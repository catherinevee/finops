#!/usr/bin/env python3
"""
GCP Cloud Scheduler Automation for FinOps Cost Optimization
This script implements automated cost optimization workflows using GCP services.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from google.cloud import compute_v1
from google.cloud import scheduler_v1
from google.cloud import functions_v2
from google.cloud import monitoring_v3
from google.cloud import billing_v1
import google.auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GCPFinOpsAutomation:
    """GCP FinOps automation class for cost optimization"""
    
    def __init__(self, project_id: str, region: str = "us-central1"):
        self.project_id = project_id
        self.region = region
        
        # Initialize clients
        self.compute_client = compute_v1.InstancesClient()
        self.scheduler_client = scheduler_v1.CloudSchedulerClient()
        self.functions_client = functions_v2.FunctionServiceClient()
        self.monitoring_client = monitoring_v3.MetricServiceClient()
        self.billing_client = billing_v1.CloudBillingClient()
        
        # Set up project paths
        self.project_path = f"projects/{project_id}"
        self.location_path = f"projects/{project_id}/locations/{region}"
    
    def get_idle_instances(self, idle_threshold_hours: int = 24) -> List[Dict]:
        """Get instances that have been idle for the specified threshold"""
        idle_instances = []
        
        try:
            # List all instances in the project
            request = compute_v1.ListInstancesRequest(project=self.project_id)
            instances = self.compute_client.list(request=request)
            
            for instance in instances:
                # Get CPU utilization metrics for the last 24 hours
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(hours=idle_threshold_hours)
                
                # Create time series filter
                filter_str = f'metric.type = "compute.googleapis.com/instance/cpu/utilization" AND resource.labels.instance_name = "{instance.name}"'
                
                request = monitoring_v3.ListTimeSeriesRequest(
                    name=self.project_path,
                    filter=filter_str,
                    interval_start_time=start_time.isoformat() + "Z",
                    interval_end_time=end_time.isoformat() + "Z"
                )
                
                time_series = self.monitoring_client.list_time_series(request=request)
                
                # Calculate average CPU utilization
                cpu_values = []
                for series in time_series:
                    for point in series.points:
                        if point.value.double_value is not None:
                            cpu_values.append(point.value.double_value)
                
                if cpu_values:
                    avg_cpu = sum(cpu_values) / len(cpu_values)
                    
                    if avg_cpu < 5:  # Less than 5% CPU usage
                        idle_instances.append({
                            'name': instance.name,
                            'zone': instance.zone.split('/')[-1],
                            'machine_type': instance.machine_type.split('/')[-1],
                            'average_cpu': avg_cpu,
                            'estimated_monthly_cost': self.estimate_instance_cost(instance.machine_type.split('/')[-1])
                        })
        
        except Exception as e:
            logger.error(f"Error getting idle instances: {e}")
        
        return idle_instances
    
    def get_unused_resources(self) -> List[Dict]:
        """Get unused resources for cleanup"""
        unused_resources = []
        
        try:
            # Check for unattached disks
            disk_client = compute_v1.DisksClient()
            request = compute_v1.ListDisksRequest(project=self.project_id)
            disks = disk_client.list(request=request)
            
            for disk in disks:
                if disk.users is None or len(disk.users) == 0:
                    unused_resources.append({
                        'type': 'Disk',
                        'name': disk.name,
                        'zone': disk.zone.split('/')[-1],
                        'size_gb': disk.size_gb,
                        'estimated_monthly_cost': self.estimate_disk_cost(disk.size_gb, disk.type_),
                        'action': 'Delete'
                    })
            
            # Check for unused external IPs
            address_client = compute_v1.AddressesClient()
            request = compute_v1.ListAddressesRequest(project=self.project_id)
            addresses = address_client.list(request=request)
            
            for address in addresses:
                if address.users is None or len(address.users) == 0:
                    unused_resources.append({
                        'type': 'External IP',
                        'name': address.name,
                        'region': address.region.split('/')[-1] if address.region else 'global',
                        'estimated_monthly_cost': 3.65,  # Standard external IP cost
                        'action': 'Delete'
                    })
        
        except Exception as e:
            logger.error(f"Error getting unused resources: {e}")
        
        return unused_resources
    
    def optimize_instance_sizes(self) -> List[Dict]:
        """Optimize instance sizes based on usage patterns"""
        optimization_recommendations = []
        
        try:
            # List all instances
            request = compute_v1.ListInstancesRequest(project=self.project_id)
            instances = self.compute_client.list(request=request)
            
            for instance in instances:
                # Get usage metrics for the last 7 days
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)
                
                # Get CPU and memory metrics
                cpu_filter = f'metric.type = "compute.googleapis.com/instance/cpu/utilization" AND resource.labels.instance_name = "{instance.name}"'
                memory_filter = f'metric.type = "compute.googleapis.com/instance/memory/utilization" AND resource.labels.instance_name = "{instance.name}"'
                
                # Get CPU metrics
                cpu_request = monitoring_v3.ListTimeSeriesRequest(
                    name=self.project_path,
                    filter=cpu_filter,
                    interval_start_time=start_time.isoformat() + "Z",
                    interval_end_time=end_time.isoformat() + "Z"
                )
                
                cpu_series = self.monitoring_client.list_time_series(cpu_request)
                cpu_values = []
                for series in cpu_series:
                    for point in series.points:
                        if point.value.double_value is not None:
                            cpu_values.append(point.value.double_value)
                
                # Get memory metrics
                memory_request = monitoring_v3.ListTimeSeriesRequest(
                    name=self.project_path,
                    filter=memory_filter,
                    interval_start_time=start_time.isoformat() + "Z",
                    interval_end_time=end_time.isoformat() + "Z"
                )
                
                memory_series = self.monitoring_client.list_time_series(memory_request)
                memory_values = []
                for series in memory_series:
                    for point in series.points:
                        if point.value.double_value is not None:
                            memory_values.append(point.value.double_value)
                
                if cpu_values and memory_values:
                    avg_cpu = sum(cpu_values) / len(cpu_values)
                    avg_memory = sum(memory_values) / len(memory_values)
                    
                    # Determine if instance is oversized
                    current_size = instance.machine_type.split('/')[-1]
                    recommended_size = self.get_recommended_instance_size(current_size, avg_cpu, avg_memory)
                    
                    if recommended_size != current_size:
                        current_cost = self.estimate_instance_cost(current_size)
                        recommended_cost = self.estimate_instance_cost(recommended_size)
                        savings = current_cost - recommended_cost
                        
                        optimization_recommendations.append({
                            'instance_name': instance.name,
                            'zone': instance.zone.split('/')[-1],
                            'current_size': current_size,
                            'recommended_size': recommended_size,
                            'average_cpu': avg_cpu,
                            'average_memory': avg_memory,
                            'monthly_savings': savings,
                            'action': 'Resize'
                        })
        
        except Exception as e:
            logger.error(f"Error optimizing instance sizes: {e}")
        
        return optimization_recommendations
    
    def schedule_instances(self) -> Dict:
        """Schedule instances based on business hours"""
        schedule_results = {
            'started': [],
            'stopped': [],
            'errors': []
        }
        
        try:
            # List all instances
            request = compute_v1.ListInstancesRequest(project=self.project_id)
            instances = self.compute_client.list(request=request)
            
            current_time = datetime.utcnow()
            current_hour = current_time.hour
            is_weekend = current_time.weekday() >= 5  # Saturday = 5, Sunday = 6
            
            for instance in instances:
                # Check if instance has schedule label
                schedule_label = instance.labels.get('schedule', '') if instance.labels else ''
                
                if schedule_label == 'business-hours':
                    # Business hours: 9 AM - 6 PM, Monday-Friday
                    should_be_running = not is_weekend and 9 <= current_hour < 18
                    is_running = instance.status == 'RUNNING'
                    
                    if should_be_running and not is_running:
                        try:
                            # Start instance
                            zone_operation_client = compute_v1.ZoneOperationsClient()
                            start_request = compute_v1.StartInstanceRequest(
                                project=self.project_id,
                                zone=instance.zone.split('/')[-1],
                                instance=instance.name
                            )
                            operation = self.compute_client.start(request=start_request)
                            
                            schedule_results['started'].append({
                                'name': instance.name,
                                'zone': instance.zone.split('/')[-1],
                                'operation': operation.name
                            })
                            
                            logger.info(f"Started instance {instance.name}")
                        
                        except Exception as e:
                            schedule_results['errors'].append({
                                'instance': instance.name,
                                'action': 'start',
                                'error': str(e)
                            })
                    
                    elif not should_be_running and is_running:
                        try:
                            # Stop instance
                            stop_request = compute_v1.StopInstanceRequest(
                                project=self.project_id,
                                zone=instance.zone.split('/')[-1],
                                instance=instance.name
                            )
                            operation = self.compute_client.stop(request=stop_request)
                            
                            schedule_results['stopped'].append({
                                'name': instance.name,
                                'zone': instance.zone.split('/')[-1],
                                'operation': operation.name
                            })
                            
                            logger.info(f"Stopped instance {instance.name}")
                        
                        except Exception as e:
                            schedule_results['errors'].append({
                                'instance': instance.name,
                                'action': 'stop',
                                'error': str(e)
                            })
        
        except Exception as e:
            logger.error(f"Error scheduling instances: {e}")
            schedule_results['errors'].append({
                'action': 'schedule',
                'error': str(e)
            })
        
        return schedule_results
    
    def create_cloud_scheduler_job(self, job_name: str, schedule: str, target_function: str) -> str:
        """Create a Cloud Scheduler job for automation"""
        try:
            # Create the job
            job = scheduler_v1.Job()
            job.name = f"{self.location_path}/jobs/{job_name}"
            job.schedule = schedule
            job.time_zone = "UTC"
            
            # Set HTTP target
            job.http_target = scheduler_v1.HttpTarget()
            job.http_target.uri = f"https://{self.region}-{self.project_id}.cloudfunctions.net/{target_function}"
            job.http_target.http_method = scheduler_v1.HttpMethod.POST
            job.http_target.headers = {
                "Content-Type": "application/json"
            }
            
            # Create the job
            request = scheduler_v1.CreateJobRequest(
                parent=self.location_path,
                job=job
            )
            
            response = self.scheduler_client.create_job(request=request)
            logger.info(f"Created Cloud Scheduler job: {response.name}")
            return response.name
        
        except Exception as e:
            logger.error(f"Error creating Cloud Scheduler job: {e}")
            raise
    
    def estimate_instance_cost(self, machine_type: str) -> float:
        """Estimate monthly cost for instance type"""
        cost_map = {
            'e2-micro': 6.11,
            'e2-small': 12.22,
            'e2-medium': 24.44,
            'n1-standard-1': 24.27,
            'n1-standard-2': 48.54,
            'n1-standard-4': 97.08,
            'n1-standard-8': 194.16
        }
        
        return cost_map.get(machine_type, 100.0)  # Default estimate
    
    def estimate_disk_cost(self, size_gb: int, disk_type: str) -> float:
        """Estimate monthly cost for disk"""
        cost_per_gb = 0.04 if 'ssd' in disk_type.lower() else 0.02
        return size_gb * cost_per_gb
    
    def get_recommended_instance_size(self, current_size: str, avg_cpu: float, avg_memory: float) -> str:
        """Get recommended instance size based on usage"""
        # Simple logic for demonstration
        if avg_cpu < 10 and 'n1-standard-4' in current_size:
            return 'n1-standard-2'
        elif avg_cpu < 20 and 'n1-standard-2' in current_size:
            return 'e2-medium'
        elif avg_cpu < 30 and 'e2-medium' in current_size:
            return 'e2-small'
        
        return current_size
    
    def generate_optimization_report(self) -> Dict:
        """Generate comprehensive optimization report"""
        try:
            idle_instances = self.get_idle_instances()
            unused_resources = self.get_unused_resources()
            optimization_recommendations = self.optimize_instance_sizes()
            schedule_results = self.schedule_instances()
            
            total_potential_savings = (
                sum(instance['estimated_monthly_cost'] for instance in idle_instances) +
                sum(resource['estimated_monthly_cost'] for resource in unused_resources) +
                sum(rec['monthly_savings'] for rec in optimization_recommendations)
            )
            
            report = {
                'generated_at': datetime.utcnow().isoformat(),
                'project_id': self.project_id,
                'region': self.region,
                'idle_instances': idle_instances,
                'unused_resources': unused_resources,
                'optimization_recommendations': optimization_recommendations,
                'schedule_results': schedule_results,
                'total_potential_savings': total_potential_savings,
                'summary': {
                    'idle_instances_count': len(idle_instances),
                    'unused_resources_count': len(unused_resources),
                    'optimization_recommendations_count': len(optimization_recommendations),
                    'instances_started': len(schedule_results['started']),
                    'instances_stopped': len(schedule_results['stopped'])
                }
            }
            
            # Log the report
            logger.info(f"Generated optimization report with ${total_potential_savings:.2f} potential monthly savings")
            
            return report
        
        except Exception as e:
            logger.error(f"Error generating optimization report: {e}")
            return {'error': str(e)}

def main():
    """Main function for GCP FinOps automation"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GCP FinOps Automation')
    parser.add_argument('--project-id', required=True, help='GCP Project ID')
    parser.add_argument('--region', default='us-central1', help='GCP Region')
    parser.add_argument('--action', choices=['report', 'schedule', 'optimize'], default='report', help='Action to perform')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without making changes')
    
    args = parser.parse_args()
    
    try:
        automation = GCPFinOpsAutomation(args.project_id, args.region)
        
        if args.action == 'report':
            report = automation.generate_optimization_report()
            print(json.dumps(report, indent=2))
        
        elif args.action == 'schedule':
            if not args.dry_run:
                results = automation.schedule_instances()
                print(json.dumps(results, indent=2))
            else:
                print("Dry run: Would schedule instances based on business hours")
        
        elif args.action == 'optimize':
            if not args.dry_run:
                recommendations = automation.optimize_instance_sizes()
                print(json.dumps(recommendations, indent=2))
            else:
                print("Dry run: Would optimize instance sizes based on usage patterns")
        
        logger.info("GCP FinOps automation completed successfully")
    
    except Exception as e:
        logger.error(f"Error in GCP FinOps automation: {e}")
        raise

if __name__ == "__main__":
    main()
