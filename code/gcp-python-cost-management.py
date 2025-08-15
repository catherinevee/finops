#!/usr/bin/env python3
"""
Google Cloud Platform (GCP) Cost Management Script
Provides comprehensive cost analysis and optimization recommendations for GCP resources.
"""

import os
from google.cloud import billing_v1
from google.cloud import compute_v1
from google.cloud import storage
from google.cloud import bigquery
from google.cloud import sqladmin_v1
from google.cloud import container_v1
import pandas as pd
from datetime import datetime, timedelta
import json

class GCPCostOptimizer:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.billing_client = billing_v1.CloudBillingClient()
        self.compute_client = compute_v1.InstancesClient()
        self.storage_client = storage.Client()
        self.bigquery_client = bigquery.Client()
        self.sql_client = sqladmin_v1.SqlAdminServiceClient()
        self.container_client = container_v1.ClusterManagerClient()
        
    def analyze_compute_instances(self) -> dict:
        """Analyze compute instances for optimization opportunities"""
        instances = []
        
        # Get all zones
        request = compute_v1.ListZonesRequest(project=self.project_id)
        zones = self.compute_client.list(request=request)
        
        for zone in zones:
            request = compute_v1.ListInstancesRequest(
                project=self.project_id,
                zone=zone.name
            )
            zone_instances = self.compute_client.list(request=request)
            
            for instance in zone_instances:
                instances.append({
                    'name': instance.name,
                    'zone': zone.name,
                    'machine_type': instance.machine_type.split('/')[-1],
                    'status': instance.status,
                    'cpu_platform': instance.cpu_platform,
                    'creation_timestamp': instance.creation_timestamp,
                    'labels': instance.labels
                })
        
        return {
            'total_instances': len(instances),
            'running_instances': len([i for i in instances if i['status'] == 'RUNNING']),
            'stopped_instances': len([i for i in instances if i['status'] == 'STOPPED']),
            'instances': instances
        }
    
    def analyze_storage_buckets(self) -> dict:
        """Analyze storage buckets for optimization opportunities"""
        buckets = self.storage_client.list_buckets()
        bucket_analysis = []
        
        for bucket in buckets:
            blobs = bucket.list_blobs()
            total_size = sum(blob.size for blob in blobs)
            
            bucket_analysis.append({
                'name': bucket.name,
                'location': bucket.location,
                'storage_class': bucket.storage_class,
                'total_size_gb': total_size / (1024**3),
                'created': bucket.time_created,
                'labels': bucket.labels
            })
        
        return {
            'total_buckets': len(bucket_analysis),
            'total_storage_gb': sum(b['total_size_gb'] for b in bucket_analysis),
            'buckets': bucket_analysis
        }
    
    def get_cost_data(self, start_date: str, end_date: str) -> dict:
        """Retrieve cost data for the specified period"""
        # Note: This is a simplified version. In production, you'd use the Billing API
        # to get detailed cost breakdowns
        return {
            'period': f"{start_date} to {end_date}",
            'total_cost': 0,  # Would be calculated from billing data
            'cost_by_service': {},
            'cost_by_region': {}
        }
    
    def generate_recommendations(self) -> list:
        """Generate cost optimization recommendations"""
        recommendations = []
        
        # Analyze instances
        instance_analysis = self.analyze_compute_instances()
        if instance_analysis['stopped_instances'] > 0:
            recommendations.append({
                'type': 'compute',
                'priority': 'high',
                'description': f"Found {instance_analysis['stopped_instances']} stopped instances that can be deleted",
                'potential_savings': 'Medium to High'
            })
        
        # Analyze storage
        storage_analysis = self.analyze_storage_buckets()
        for bucket in storage_analysis['buckets']:
            if bucket['storage_class'] == 'STANDARD' and bucket['total_size_gb'] > 100:
                recommendations.append({
                    'type': 'storage',
                    'priority': 'medium',
                    'description': f"Consider moving large files in bucket {bucket['name']} to Nearline or Coldline storage",
                    'potential_savings': 'Medium'
                })
        
        return recommendations

    def analyze_bigquery(self) -> None:
        """Analyze BigQuery for optimization"""
        try:
            # List all datasets
            datasets = list(self.bigquery_client.list_datasets())
            
            print("=== BigQuery Analysis ===")
            print(f"Total datasets: {len(datasets)}")
            
            total_tables = 0
            total_views = 0
            
            for dataset in datasets:
                dataset_ref = self.bigquery_client.dataset(dataset.dataset_id)
                tables = list(self.bigquery_client.list_tables(dataset_ref))
                
                for table in tables:
                    table_ref = dataset_ref.table(table.table_id)
                    table_obj = self.bigquery_client.get_table(table_ref)
                    
                    if table_obj.table_type == 'TABLE':
                        total_tables += 1
                        # Check for large tables that could benefit from partitioning
                        if table_obj.num_rows and table_obj.num_rows > 1000000:
                            print(f"  Large table: {dataset.dataset_id}.{table.table_id} ({table_obj.num_rows:,} rows)")
                    elif table_obj.table_type == 'VIEW':
                        total_views += 1
            
            print(f"Total tables: {total_tables}")
            print(f"Total views: {total_views}")
            
            # Check for unused datasets (simplified check)
            print("\nRecommendations:")
            print("• Consider partitioning large tables for better query performance")
            print("• Review and delete unused datasets to reduce storage costs")
            print("• Use materialized views for frequently accessed data")
            
        except Exception as e:
            print(f"Error analyzing BigQuery: {e}")

    def analyze_cloud_sql(self) -> None:
        """Analyze Cloud SQL instances"""
        try:
            # List all Cloud SQL instances
            request = sqladmin_v1.SqlInstancesListRequest(project=self.project_id)
            instances = self.sql_client.list(request=request)
            
            print("=== Cloud SQL Analysis ===")
            print(f"Total instances: {len(instances.items)}")
            
            for instance in instances.items:
                print(f"\nInstance: {instance.name}")
                print(f"  Database version: {instance.database_version}")
                print(f"  Region: {instance.region}")
                print(f"  State: {instance.state}")
                
                if instance.settings:
                    settings = instance.settings
                    print(f"  Machine type: {settings.tier}")
                    print(f"  Storage size: {settings.data_disk_size_gb} GB")
                    
                    # Check for optimization opportunities
                    if settings.data_disk_size_gb > 100:
                        print(f"  ⚠️  Large storage size - consider archiving old data")
                    
                    if settings.tier and 'db-f1-micro' in settings.tier:
                        print(f"  ⚠️  Using micro instance - consider upgrading for better performance")
            
            print("\nRecommendations:")
            print("• Right-size instances based on actual usage patterns")
            print("• Enable automated backups with appropriate retention")
            print("• Consider using Cloud SQL Proxy for secure connections")
            
        except Exception as e:
            print(f"Error analyzing Cloud SQL: {e}")

    def analyze_gke_clusters(self) -> None:
        """Analyze GKE clusters for optimization"""
        try:
            # List all GKE clusters
            parent = f"projects/{self.project_id}/locations/-"
            request = container_v1.ListClustersRequest(parent=parent)
            clusters = self.container_client.list_clusters(request=request)
            
            print("=== GKE Cluster Analysis ===")
            print(f"Total clusters: {len(clusters.clusters)}")
            
            total_nodes = 0
            total_pods = 0
            
            for cluster in clusters.clusters:
                print(f"\nCluster: {cluster.name}")
                print(f"  Location: {cluster.location}")
                print(f"  Version: {cluster.current_master_version}")
                print(f"  Node count: {cluster.current_node_count}")
                print(f"  Status: {cluster.status}")
                
                total_nodes += cluster.current_node_count
                
                # Check for optimization opportunities
                if cluster.current_node_count > 10:
                    print(f"  ⚠️  Large cluster - consider node pools for better resource management")
                
                if cluster.autopilot:
                    print(f"  ✓ Using Autopilot - automatic optimization enabled")
                else:
                    print(f"  ⚠️  Standard cluster - consider Autopilot for cost optimization")
                
                # Analyze node pools
                if hasattr(cluster, 'node_pools'):
                    for pool in cluster.node_pools:
                        print(f"    Node pool: {pool.name}")
                        print(f"      Machine type: {pool.config.machine_type}")
                        print(f"      Node count: {pool.initial_node_count}")
                        
                        # Check for spot instances
                        if hasattr(pool.config, 'spot') and pool.config.spot:
                            print(f"      ✓ Using spot instances for cost savings")
                        else:
                            print(f"      ⚠️  Consider spot instances for non-critical workloads")
            
            print(f"\nTotal nodes across all clusters: {total_nodes}")
            print(f"Total pods: {total_pods}")
            
            print("\nRecommendations:")
            print("• Use Autopilot clusters for automatic optimization")
            print("• Implement horizontal pod autoscaling")
            print("• Use spot instances for non-critical workloads")
            print("• Right-size node pools based on actual resource usage")
            
        except Exception as e:
            print(f"Error analyzing GKE clusters: {e}")

def main():
    """Main function to run GCP cost optimization analysis"""
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
    if not project_id:
        print("Please set GOOGLE_CLOUD_PROJECT environment variable")
        return
    
    optimizer = GCPCostOptimizer(project_id)
    
    print("GCP Cost Optimization Analysis")
    print("=" * 40)
    
    # Run comprehensive analysis
    optimizer.analyze_bigquery()
    print()
    optimizer.analyze_cloud_sql()
    print()
    optimizer.analyze_gke_clusters()
    print()
    
    # Generate recommendations
    recommendations = optimizer.generate_recommendations()
    
    print("Cost Optimization Recommendations:")
    print("=" * 40)
    for i, rec in enumerate(recommendations, 1):
        print(f"{i}. [{rec['priority'].upper()}] {rec['description']}")
        print(f"   Potential savings: {rec['potential_savings']}")
        print()

if __name__ == "__main__":
    main()
