#!/usr/bin/env python3
"""
Multi-Cloud Cost Aggregator
Aggregates costs across AWS, Azure, GCP, and Digital Ocean
"""

import os
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import boto3
from azure.identity import DefaultAzureCredential
from azure.mgmt.costmanagement import CostManagementClient
from google.cloud import billing_v1
import requests

class MultiCloudCostAggregator:
    def __init__(self):
        self.aws_session = None
        self.azure_client = None
        self.gcp_client = None
        self.do_token = None
        
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize cloud provider clients"""
        # AWS
        try:
            self.aws_session = boto3.Session()
            print("✓ AWS client initialized")
        except Exception as e:
            print(f"✗ AWS client initialization failed: {e}")
        
        # Azure
        try:
            credential = DefaultAzureCredential()
            self.azure_client = CostManagementClient(credential)
            print("✓ Azure client initialized")
        except Exception as e:
            print(f"✗ Azure client initialization failed: {e}")
        
        # GCP
        try:
            self.gcp_client = billing_v1.CloudBillingClient()
            print("✓ GCP client initialized")
        except Exception as e:
            print(f"✗ GCP client initialization failed: {e}")
        
        # Digital Ocean
        self.do_token = os.getenv('DIGITALOCEAN_API_TOKEN')
        if self.do_token:
            print("✓ Digital Ocean token found")
        else:
            print("✗ Digital Ocean token not found")
    
    def get_aws_costs(self, start_date: str, end_date: str) -> Dict:
        """Get AWS costs for the specified period"""
        if not self.aws_session:
            return {"error": "AWS client not initialized"}
        
        try:
            ce_client = self.aws_session.client('ce')
            
            response = ce_client.get_cost_and_usage(
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
                "provider": "AWS",
                "total_cost": 0,
                "cost_by_service": {},
                "cost_by_region": {},
                "period": f"{start_date} to {end_date}"
            }
            
            for result in response['ResultsByTime']:
                for group in result['Groups']:
                    keys = group['Keys']
                    service = keys[0]
                    region = keys[1]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    
                    costs["total_cost"] += cost
                    costs["cost_by_service"][service] = costs["cost_by_service"].get(service, 0) + cost
                    costs["cost_by_region"][region] = costs["cost_by_region"].get(region, 0) + cost
            
            return costs
            
        except Exception as e:
            return {"error": f"AWS cost retrieval failed: {e}"}
    
    def get_azure_costs(self, start_date: str, end_date: str, subscription_id: str) -> Dict:
        """Get Azure costs for the specified period"""
        if not self.azure_client:
            return {"error": "Azure client not initialized"}
        
        try:
            # Convert dates to datetime objects
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            
            # Query cost data
            query = {
                "type": "Usage",
                "timeframe": "Custom",
                "timePeriod": {
                    "from": start_dt.isoformat(),
                    "to": end_dt.isoformat()
                },
                "dataset": {
                    "granularity": "Monthly",
                    "grouping": [
                        {"type": "Dimension", "usage": "SIGNED"},
                        {"type": "Dimension", "usage": "SIGNED"}
                    ]
                }
            }
            
            result = self.azure_client.query.usage(
                scope=f"/subscriptions/{subscription_id}",
                parameters=query
            )
            
            costs = {
                "provider": "Azure",
                "total_cost": 0,
                "cost_by_service": {},
                "cost_by_region": {},
                "period": f"{start_date} to {end_date}"
            }
            
            # Process results (simplified - actual implementation would parse the result structure)
            # This is a placeholder for the actual cost calculation logic
            
            return costs
            
        except Exception as e:
            return {"error": f"Azure cost retrieval failed: {e}"}
    
    def get_gcp_costs(self, start_date: str, end_date: str, project_id: str) -> Dict:
        """Get GCP costs for the specified period"""
        if not self.gcp_client:
            return {"error": "GCP client not initialized"}
        
        try:
            # Note: This is a simplified version. In production, you'd use the Billing API
            # to get detailed cost breakdowns from BigQuery billing export
            
            costs = {
                "provider": "GCP",
                "total_cost": 0,
                "cost_by_service": {},
                "cost_by_region": {},
                "period": f"{start_date} to {end_date}",
                "note": "Cost data would be retrieved from BigQuery billing export"
            }
            
            return costs
            
        except Exception as e:
            return {"error": f"GCP cost retrieval failed: {e}"}
    
    def get_digitalocean_costs(self, start_date: str, end_date: str) -> Dict:
        """Get Digital Ocean costs for the specified period"""
        if not self.do_token:
            return {"error": "Digital Ocean token not found"}
        
        try:
            headers = {
                "Authorization": f"Bearer {self.do_token}",
                "Content-Type": "application/json"
            }
            
            # Get droplets
            droplets_response = requests.get(
                "https://api.digitalocean.com/v2/droplets",
                headers=headers
            )
            droplets_response.raise_for_status()
            
            # Get databases
            databases_response = requests.get(
                "https://api.digitalocean.com/v2/databases",
                headers=headers
            )
            databases_response.raise_for_status()
            
            # Calculate costs (simplified)
            droplets = droplets_response.json().get("droplets", [])
            databases = databases_response.json().get("databases", [])
            
            total_droplet_cost = sum(self._get_do_droplet_cost(droplet) for droplet in droplets)
            total_database_cost = sum(self._get_do_database_cost(db) for db in databases)
            
            costs = {
                "provider": "Digital Ocean",
                "total_cost": total_droplet_cost + total_database_cost,
                "cost_by_service": {
                    "droplets": total_droplet_cost,
                    "databases": total_database_cost
                },
                "cost_by_region": {},
                "period": f"{start_date} to {end_date}"
            }
            
            return costs
            
        except Exception as e:
            return {"error": f"Digital Ocean cost retrieval failed: {e}"}
    
    def _get_do_droplet_cost(self, droplet: Dict) -> float:
        """Calculate monthly cost for a Digital Ocean droplet"""
        size_slug = droplet.get("size_slug", "")
        pricing = {
            "s-1vcpu-1gb": 5.00,
            "s-1vcpu-2gb": 10.00,
            "s-2vcpu-2gb": 15.00,
            "s-2vcpu-4gb": 20.00,
            "s-4vcpu-8gb": 40.00,
            "s-6vcpu-16gb": 80.00,
            "s-8vcpu-32gb": 160.00
        }
        return pricing.get(size_slug, 0.0)
    
    def _get_do_database_cost(self, database: Dict) -> float:
        """Calculate monthly cost for a Digital Ocean database"""
        size_slug = database.get("size", "")
        pricing = {
            "db-s-1vcpu-1gb": 15.00,
            "db-s-1vcpu-2gb": 30.00,
            "db-s-2vcpu-4gb": 60.00,
            "db-s-4vcpu-8gb": 120.00
        }
        return pricing.get(size_slug, 0.0)
    
    def aggregate_costs(self, start_date: str, end_date: str, 
                       azure_subscription_id: str = None, 
                       gcp_project_id: str = None) -> Dict:
        """Aggregate costs from all cloud providers"""
        aggregated_costs = {
            "period": f"{start_date} to {end_date}",
            "total_cost": 0,
            "cost_by_provider": {},
            "cost_by_service": {},
            "cost_by_region": {},
            "providers": []
        }
        
        # Get costs from each provider
        aws_costs = self.get_aws_costs(start_date, end_date)
        if "error" not in aws_costs:
            aggregated_costs["cost_by_provider"]["AWS"] = aws_costs["total_cost"]
            aggregated_costs["total_cost"] += aws_costs["total_cost"]
            aggregated_costs["providers"].append("AWS")
            
            # Merge service costs
            for service, cost in aws_costs["cost_by_service"].items():
                aggregated_costs["cost_by_service"][f"AWS-{service}"] = cost
        
        if azure_subscription_id:
            azure_costs = self.get_azure_costs(start_date, end_date, azure_subscription_id)
            if "error" not in azure_costs:
                aggregated_costs["cost_by_provider"]["Azure"] = azure_costs["total_cost"]
                aggregated_costs["total_cost"] += azure_costs["total_cost"]
                aggregated_costs["providers"].append("Azure")
                
                for service, cost in azure_costs["cost_by_service"].items():
                    aggregated_costs["cost_by_service"][f"Azure-{service}"] = cost
        
        if gcp_project_id:
            gcp_costs = self.get_gcp_costs(start_date, end_date, gcp_project_id)
            if "error" not in gcp_costs:
                aggregated_costs["cost_by_provider"]["GCP"] = gcp_costs["total_cost"]
                aggregated_costs["total_cost"] += gcp_costs["total_cost"]
                aggregated_costs["providers"].append("GCP")
                
                for service, cost in gcp_costs["cost_by_service"].items():
                    aggregated_costs["cost_by_service"][f"GCP-{service}"] = cost
        
        do_costs = self.get_digitalocean_costs(start_date, end_date)
        if "error" not in do_costs:
            aggregated_costs["cost_by_provider"]["Digital Ocean"] = do_costs["total_cost"]
            aggregated_costs["total_cost"] += do_costs["total_cost"]
            aggregated_costs["providers"].append("Digital Ocean")
            
            for service, cost in do_costs["cost_by_service"].items():
                aggregated_costs["cost_by_service"][f"DO-{service}"] = cost
        
        return aggregated_costs
    
    def generate_cost_report(self, start_date: str, end_date: str,
                           azure_subscription_id: str = None,
                           gcp_project_id: str = None) -> str:
        """Generate a comprehensive cost report"""
        aggregated_costs = self.aggregate_costs(
            start_date, end_date, azure_subscription_id, gcp_project_id
        )
        
        report = f"""
Multi-Cloud Cost Aggregation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Period: {aggregated_costs['period']}

TOTAL COSTS:
- Total Cost: ${aggregated_costs['total_cost']:.2f}

COST BY PROVIDER:
"""
        
        for provider, cost in aggregated_costs["cost_by_provider"].items():
            percentage = (cost / aggregated_costs["total_cost"] * 100) if aggregated_costs["total_cost"] > 0 else 0
            report += f"- {provider}: ${cost:.2f} ({percentage:.1f}%)\n"
        
        report += "\nTOP SERVICES BY COST:\n"
        sorted_services = sorted(
            aggregated_costs["cost_by_service"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        for service, cost in sorted_services:
            percentage = (cost / aggregated_costs["total_cost"] * 100) if aggregated_costs["total_cost"] > 0 else 0
            report += f"- {service}: ${cost:.2f} ({percentage:.1f}%)\n"
        
        report += f"\nACTIVE PROVIDERS: {', '.join(aggregated_costs['providers'])}"
        
        return report

def main():
    """Main function to run multi-cloud cost aggregation"""
    aggregator = MultiCloudCostAggregator()
    
    # Set date range for last month
    end_date = datetime.now().replace(day=1) - timedelta(days=1)
    start_date = end_date.replace(day=1)
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')
    
    print("Multi-Cloud Cost Aggregation")
    print("=" * 40)
    
    # Generate cost report
    report = aggregator.generate_cost_report(
        start_date_str, 
        end_date_str,
        azure_subscription_id=os.getenv('AZURE_SUBSCRIPTION_ID'),
        gcp_project_id=os.getenv('GOOGLE_CLOUD_PROJECT')
    )
    
    print(report)
    
    # Save detailed data to JSON
    aggregated_costs = aggregator.aggregate_costs(
        start_date_str, 
        end_date_str,
        azure_subscription_id=os.getenv('AZURE_SUBSCRIPTION_ID'),
        gcp_project_id=os.getenv('GOOGLE_CLOUD_PROJECT')
    )
    
    with open('multicloud_costs.json', 'w') as f:
        json.dump(aggregated_costs, f, indent=2, default=str)
    
    print(f"\nDetailed cost data saved to multicloud_costs.json")

if __name__ == "__main__":
    main()
