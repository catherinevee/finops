#!/usr/bin/env python3
"""
AWS Comprehensive Cost Optimizer
Analyzes and optimizes AWS resources for cost efficiency
"""

import os
import boto3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

class AWSCostOptimizer:
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.rds_client = boto3.client('rds', region_name=region)
        self.ce_client = boto3.client('ce', region_name=region)
        self.compute_optimizer_client = boto3.client('compute-optimizer', region_name=region)
        self.s3_client = boto3.client('s3')
        self.elasticache_client = boto3.client('elasticache', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        
    def analyze_ec2_instances(self) -> Dict:
        """Analyze EC2 instances for optimization opportunities"""
        try:
            # Get all instances
            response = self.ec2_client.describe_instances()
            instances = []
            
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    instances.append({
                        'instance_id': instance['InstanceId'],
                        'instance_type': instance['InstanceType'],
                        'state': instance['State']['Name'],
                        'launch_time': instance['LaunchTime'],
                        'platform': instance.get('Platform', 'linux'),
                        'vpc_id': instance.get('VpcId'),
                        'subnet_id': instance.get('SubnetId'),
                        'tags': {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
                    })
            
            # Get Compute Optimizer recommendations
            optimizer_recommendations = self._get_compute_optimizer_recommendations()
            
            analysis = {
                'total_instances': len(instances),
                'running_instances': len([i for i in instances if i['state'] == 'running']),
                'stopped_instances': len([i for i in instances if i['state'] == 'stopped']),
                'terminated_instances': len([i for i in instances if i['state'] == 'terminated']),
                'instances': instances,
                'optimizer_recommendations': optimizer_recommendations,
                'optimization_opportunities': []
            }
            
            # Identify optimization opportunities
            for instance in instances:
                if instance['state'] == 'stopped':
                    analysis['optimization_opportunities'].append({
                        'type': 'stopped_instance',
                        'instance_id': instance['instance_id'],
                        'action': 'Terminate stopped instance',
                        'potential_savings': self._estimate_instance_cost(instance['instance_type'])
                    })
                
                elif instance['state'] == 'running':
                    # Check for oversized instances
                    if self._is_instance_oversized(instance['instance_type']):
                        analysis['optimization_opportunities'].append({
                            'type': 'oversized_instance',
                            'instance_id': instance['instance_id'],
                            'current_type': instance['instance_type'],
                            'recommended_type': self._get_recommended_instance_type(instance['instance_type']),
                            'action': 'Downsize instance',
                            'potential_savings': self._estimate_downsizing_savings(instance['instance_type'])
                        })
            
            return analysis
            
        except Exception as e:
            return {'error': f'EC2 analysis failed: {e}'}
    
    def analyze_rds_instances(self) -> Dict:
        """Analyze RDS instances for optimization opportunities"""
        try:
            response = self.rds_client.describe_db_instances()
            instances = response['DBInstances']
            
            analysis = {
                'total_instances': len(instances),
                'instances': [],
                'optimization_opportunities': []
            }
            
            for instance in instances:
                instance_data = {
                    'db_instance_identifier': instance['DBInstanceIdentifier'],
                    'engine': instance['Engine'],
                    'db_instance_class': instance['DBInstanceClass'],
                    'db_instance_status': instance['DBInstanceStatus'],
                    'allocated_storage': instance.get('AllocatedStorage', 0),
                    'storage_type': instance.get('StorageType', 'standard'),
                    'multi_az': instance.get('MultiAZ', False),
                    'backup_retention_period': instance.get('BackupRetentionPeriod', 0)
                }
                
                analysis['instances'].append(instance_data)
                
                # Check for optimization opportunities
                if instance['DBInstanceStatus'] == 'stopped':
                    analysis['optimization_opportunities'].append({
                        'type': 'stopped_rds',
                        'instance_id': instance['DBInstanceIdentifier'],
                        'action': 'Delete stopped RDS instance',
                        'potential_savings': self._estimate_rds_cost(instance['DBInstanceClass'])
                    })
                
                # Check for oversized instances
                if self._is_rds_oversized(instance['DBInstanceClass']):
                    analysis['optimization_opportunities'].append({
                        'type': 'oversized_rds',
                        'instance_id': instance['DBInstanceIdentifier'],
                        'current_class': instance['DBInstanceClass'],
                        'recommended_class': self._get_recommended_rds_class(instance['DBInstanceClass']),
                        'action': 'Downsize RDS instance',
                        'potential_savings': self._estimate_rds_downsizing_savings(instance['DBInstanceClass'])
                    })
            
            return analysis
            
        except Exception as e:
            return {'error': f'RDS analysis failed: {e}'}
    
    def analyze_s3_buckets(self) -> Dict:
        """Analyze S3 buckets for optimization opportunities"""
        try:
            response = self.s3_client.list_buckets()
            buckets = response['Buckets']
            
            analysis = {
                'total_buckets': len(buckets),
                'buckets': [],
                'optimization_opportunities': []
            }
            
            for bucket in buckets:
                try:
                    # Get bucket location
                    location_response = self.s3_client.get_bucket_location(Bucket=bucket['Name'])
                    region = location_response.get('LocationConstraint') or 'us-east-1'
                    
                    # Get bucket size (simplified)
                    bucket_data = {
                        'name': bucket['Name'],
                        'creation_date': bucket['CreationDate'],
                        'region': region
                    }
                    
                    analysis['buckets'].append(bucket_data)
                    
                    # Check for lifecycle policies
                    try:
                        lifecycle_response = self.s3_client.get_bucket_lifecycle_configuration(Bucket=bucket['Name'])
                        bucket_data['has_lifecycle_policy'] = True
                    except:
                        bucket_data['has_lifecycle_policy'] = False
                        analysis['optimization_opportunities'].append({
                            'type': 'no_lifecycle_policy',
                            'bucket_name': bucket['Name'],
                            'action': 'Add lifecycle policy for cost optimization',
                            'potential_savings': 'Medium'
                        })
                
                except Exception as e:
                    print(f"Error analyzing bucket {bucket['Name']}: {e}")
            
            return analysis
            
        except Exception as e:
            return {'error': f'S3 analysis failed: {e}'}
    
    def analyze_elasticache_clusters(self) -> Dict:
        """Analyze ElastiCache clusters for optimization opportunities"""
        try:
            response = self.elasticache_client.describe_cache_clusters()
            clusters = response['CacheClusters']
            
            analysis = {
                'total_clusters': len(clusters),
                'clusters': [],
                'optimization_opportunities': []
            }
            
            for cluster in clusters:
                cluster_data = {
                    'cache_cluster_id': cluster['CacheClusterId'],
                    'engine': cluster['Engine'],
                    'cache_node_type': cluster['CacheNodeType'],
                    'cache_cluster_status': cluster['CacheClusterStatus'],
                    'num_cache_nodes': cluster['NumCacheNodes']
                }
                
                analysis['clusters'].append(cluster_data)
                
                # Check for optimization opportunities
                if cluster['CacheClusterStatus'] == 'available':
                    if self._is_elasticache_oversized(cluster['CacheNodeType']):
                        analysis['optimization_opportunities'].append({
                            'type': 'oversized_elasticache',
                            'cluster_id': cluster['CacheClusterId'],
                            'current_type': cluster['CacheNodeType'],
                            'recommended_type': self._get_recommended_elasticache_type(cluster['CacheNodeType']),
                            'action': 'Downsize ElastiCache cluster',
                            'potential_savings': 'Medium'
                        })
            
            return analysis
            
        except Exception as e:
            return {'error': f'ElastiCache analysis failed: {e}'}
    
    def analyze_lambda_functions(self) -> Dict:
        """Analyze Lambda functions for optimization opportunities"""
        try:
            response = self.lambda_client.list_functions()
            functions = response['Functions']
            
            analysis = {
                'total_functions': len(functions),
                'functions': [],
                'optimization_opportunities': []
            }
            
            for function in functions:
                function_data = {
                    'function_name': function['FunctionName'],
                    'runtime': function['Runtime'],
                    'memory_size': function['MemorySize'],
                    'timeout': function['Timeout'],
                    'last_modified': function['LastModified']
                }
                
                analysis['functions'].append(function_data)
                
                # Check for optimization opportunities
                if function['MemorySize'] > 1024:  # Over 1GB memory
                    analysis['optimization_opportunities'].append({
                        'type': 'high_memory_lambda',
                        'function_name': function['FunctionName'],
                        'current_memory': function['MemorySize'],
                        'action': 'Optimize Lambda memory allocation',
                        'potential_savings': 'Low to Medium'
                    })
            
            return analysis
            
        except Exception as e:
            return {'error': f'Lambda analysis failed: {e}'}
    
    def get_cost_data(self, start_date: str, end_date: str) -> Dict:
        """Get cost data for the specified period"""
        try:
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date,
                    'End': end_date
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )
            
            costs = {
                'period': f"{start_date} to {end_date}",
                'total_cost': 0,
                'cost_by_service': {},
                'cost_by_region': {}
            }
            
            for result in response['ResultsByTime']:
                for group in result['Groups']:
                    keys = group['Keys']
                    service = keys[0]
                    region = keys[1]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    
                    costs['total_cost'] += cost
                    costs['cost_by_service'][service] = costs['cost_by_service'].get(service, 0) + cost
                    costs['cost_by_region'][region] = costs['cost_by_region'].get(region, 0) + cost
            
            return costs
            
        except Exception as e:
            return {'error': f'Cost data retrieval failed: {e}'}
    
    def generate_optimization_report(self) -> str:
        """Generate comprehensive optimization report"""
        # Run all analyses
        ec2_analysis = self.analyze_ec2_instances()
        rds_analysis = self.analyze_rds_instances()
        s3_analysis = self.analyze_s3_buckets()
        elasticache_analysis = self.analyze_elasticache_clusters()
        lambda_analysis = self.analyze_lambda_functions()
        
        # Get cost data for last month
        end_date = datetime.now().replace(day=1) - timedelta(days=1)
        start_date = end_date.replace(day=1)
        cost_data = self.get_cost_data(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        report = f"""
AWS Cost Optimization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Region: {self.region}

COST SUMMARY:
- Total Cost (Last Month): ${cost_data.get('total_cost', 0):.2f}
- Top Services by Cost:
"""
        
        if 'cost_by_service' in cost_data:
            sorted_services = sorted(
                cost_data['cost_by_service'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            for service, cost in sorted_services:
                report += f"  • {service}: ${cost:.2f}\n"
        
        report += f"""
RESOURCE ANALYSIS:
- EC2 Instances: {ec2_analysis.get('total_instances', 0)} total ({ec2_analysis.get('running_instances', 0)} running)
- RDS Instances: {rds_analysis.get('total_instances', 0)} total
- S3 Buckets: {s3_analysis.get('total_buckets', 0)} total
- ElastiCache Clusters: {elasticache_analysis.get('total_clusters', 0)} total
- Lambda Functions: {lambda_analysis.get('total_functions', 0)} total

OPTIMIZATION OPPORTUNITIES:
"""
        
        # Combine all optimization opportunities
        all_opportunities = []
        all_opportunities.extend(ec2_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(rds_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(s3_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(elasticache_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(lambda_analysis.get('optimization_opportunities', []))
        
        for i, opportunity in enumerate(all_opportunities, 1):
            report += f"""
{i}. {opportunity['action']}
   - Type: {opportunity['type']}
   - Resource: {opportunity.get('instance_id', opportunity.get('bucket_name', opportunity.get('function_name', 'N/A')))}
   - Potential Savings: {opportunity.get('potential_savings', 'N/A')}
"""
        
        return report
    
    def _get_compute_optimizer_recommendations(self) -> List[Dict]:
        """Get Compute Optimizer recommendations"""
        try:
            response = self.compute_optimizer_client.get_ec2_instance_recommendations()
            return response.get('instanceRecommendations', [])
        except Exception as e:
            print(f"Compute Optimizer recommendations failed: {e}")
            return []
    
    def _estimate_instance_cost(self, instance_type: str) -> float:
        """Estimate monthly cost for an instance type"""
        # Simplified pricing - in production, you'd fetch from AWS Pricing API
        pricing = {
            't3.micro': 8.47,
            't3.small': 16.94,
            't3.medium': 33.88,
            'm5.large': 86.40,
            'm5.xlarge': 172.80,
            'c5.large': 68.40,
            'c5.xlarge': 136.80
        }
        return pricing.get(instance_type, 50.0)
    
    def _is_instance_oversized(self, instance_type: str) -> bool:
        """Check if instance type is oversized"""
        oversized_types = ['m5.2xlarge', 'm5.4xlarge', 'c5.2xlarge', 'c5.4xlarge', 'r5.2xlarge', 'r5.4xlarge']
        return instance_type in oversized_types
    
    def _get_recommended_instance_type(self, current_type: str) -> str:
        """Get recommended instance type for downsizing"""
        recommendations = {
            'm5.2xlarge': 'm5.xlarge',
            'm5.4xlarge': 'm5.2xlarge',
            'c5.2xlarge': 'c5.xlarge',
            'c5.4xlarge': 'c5.2xlarge',
            'r5.2xlarge': 'r5.xlarge',
            'r5.4xlarge': 'r5.2xlarge'
        }
        return recommendations.get(current_type, current_type)
    
    def _estimate_downsizing_savings(self, instance_type: str) -> str:
        """Estimate savings from downsizing"""
        return "30-50% of current cost"
    
    def _estimate_rds_cost(self, instance_class: str) -> str:
        """Estimate RDS instance cost"""
        return "Medium to High"
    
    def _is_rds_oversized(self, instance_class: str) -> bool:
        """Check if RDS instance is oversized"""
        oversized_classes = ['db.r5.2xlarge', 'db.r5.4xlarge', 'db.m5.2xlarge', 'db.m5.4xlarge']
        return instance_class in oversized_classes
    
    def _get_recommended_rds_class(self, current_class: str) -> str:
        """Get recommended RDS instance class"""
        recommendations = {
            'db.r5.2xlarge': 'db.r5.xlarge',
            'db.r5.4xlarge': 'db.r5.2xlarge',
            'db.m5.2xlarge': 'db.m5.xlarge',
            'db.m5.4xlarge': 'db.m5.2xlarge'
        }
        return recommendations.get(current_class, current_class)
    
    def _estimate_rds_downsizing_savings(self, instance_class: str) -> str:
        """Estimate RDS downsizing savings"""
        return "30-50% of current cost"
    
    def _is_elasticache_oversized(self, node_type: str) -> bool:
        """Check if ElastiCache node is oversized"""
        oversized_types = ['cache.r5.2xlarge', 'cache.r5.4xlarge', 'cache.m5.2xlarge', 'cache.m5.4xlarge']
        return node_type in oversized_types
    
    def _get_recommended_elasticache_type(self, current_type: str) -> str:
        """Get recommended ElastiCache node type"""
        recommendations = {
            'cache.r5.2xlarge': 'cache.r5.xlarge',
            'cache.r5.4xlarge': 'cache.r5.2xlarge',
            'cache.m5.2xlarge': 'cache.m5.xlarge',
            'cache.m5.4xlarge': 'cache.m5.2xlarge'
        }
        return recommendations.get(current_type, current_type)

def main():
    """Main function to run AWS cost optimization analysis"""
    optimizer = AWSCostOptimizer()
    
    print("AWS Cost Optimization Analysis")
    print("=" * 40)
    
    # Generate and print the optimization report
    report = optimizer.generate_optimization_report()
    print(report)
    
    # Save detailed analysis to JSON
    detailed_analysis = {
        'ec2': optimizer.analyze_ec2_instances(),
        'rds': optimizer.analyze_rds_instances(),
        's3': optimizer.analyze_s3_buckets(),
        'elasticache': optimizer.analyze_elasticache_clusters(),
        'lambda': optimizer.analyze_lambda_functions()
    }
    
    with open('aws_optimization_analysis.json', 'w') as f:
        json.dump(detailed_analysis, f, indent=2, default=str)
    
    print(f"\nDetailed analysis saved to aws_optimization_analysis.json")

if __name__ == "__main__":
    main()
