#!/usr/bin/env python3
"""
Digital Ocean Cost Optimizer
Analyzes DO resources for cost optimization opportunities
"""

import os
import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd

class DigitalOceanOptimizer:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.digitalocean.com/v2"
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, endpoint: str, method: str = "GET", data: dict = None) -> dict:
        """Make API request to Digital Ocean"""
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, headers=self.headers, json=data)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {}
    
    def analyze_droplets(self) -> Dict:
        """Analyze droplets for optimization opportunities"""
        droplets_data = self._make_request("droplets")
        droplets = droplets_data.get("droplets", [])
        
        analysis = {
            "total_droplets": len(droplets),
            "running_droplets": 0,
            "stopped_droplets": 0,
            "total_monthly_cost": 0,
            "optimization_opportunities": []
        }
        
        for droplet in droplets:
            status = droplet.get("status", "")
            if status == "active":
                analysis["running_droplets"] += 1
            elif status == "off":
                analysis["stopped_droplets"] += 1
            
            # Calculate monthly cost
            size_slug = droplet.get("size_slug", "")
            monthly_cost = self._get_droplet_monthly_cost(size_slug)
            analysis["total_monthly_cost"] += monthly_cost
            
            # Check for optimization opportunities
            if status == "off":
                analysis["optimization_opportunities"].append({
                    "type": "stopped_droplet",
                    "droplet_id": droplet["id"],
                    "name": droplet["name"],
                    "monthly_savings": monthly_cost,
                    "action": "Delete stopped droplet"
                })
            
            # Check for oversized droplets
            if self._is_droplet_oversized(droplet):
                analysis["optimization_opportunities"].append({
                    "type": "oversized_droplet",
                    "droplet_id": droplet["id"],
                    "name": droplet["name"],
                    "current_size": size_slug,
                    "recommended_size": self._get_recommended_size(size_slug),
                    "monthly_savings": monthly_cost * 0.3,  # Estimate 30% savings
                    "action": "Downsize droplet"
                })
        
        return analysis
    
    def analyze_volumes(self) -> Dict:
        """Analyze volumes for optimization opportunities"""
        volumes_data = self._make_request("volumes")
        volumes = volumes_data.get("volumes", [])
        
        analysis = {
            "total_volumes": len(volumes),
            "total_size_gb": 0,
            "unattached_volumes": 0,
            "optimization_opportunities": []
        }
        
        for volume in volumes:
            size_gb = volume.get("size_gigabytes", 0)
            analysis["total_size_gb"] += size_gb
            
            # Check for unattached volumes
            droplet_ids = volume.get("droplet_ids", [])
            if not droplet_ids:
                analysis["unattached_volumes"] += 1
                monthly_cost = size_gb * 0.10  # $0.10 per GB per month
                analysis["optimization_opportunities"].append({
                    "type": "unattached_volume",
                    "volume_id": volume["id"],
                    "name": volume["name"],
                    "size_gb": size_gb,
                    "monthly_savings": monthly_cost,
                    "action": "Delete unattached volume"
                })
        
        return analysis
    
    def analyze_databases(self) -> Dict:
        """Analyze managed databases for optimization opportunities"""
        databases_data = self._make_request("databases")
        databases = databases_data.get("databases", [])
        
        analysis = {
            "total_databases": len(databases),
            "total_monthly_cost": 0,
            "optimization_opportunities": []
        }
        
        for database in databases:
            size_slug = database.get("size", "")
            monthly_cost = self._get_database_monthly_cost(size_slug)
            analysis["total_monthly_cost"] += monthly_cost
            
            # Check for unused databases
            status = database.get("status", "")
            if status == "inactive":
                analysis["optimization_opportunities"].append({
                    "type": "inactive_database",
                    "database_id": database["id"],
                    "name": database["name"],
                    "monthly_savings": monthly_cost,
                    "action": "Delete inactive database"
                })
        
        return analysis
    
    def analyze_load_balancers(self) -> Dict:
        """Analyze load balancers for optimization opportunities"""
        load_balancers_data = self._make_request("load_balancers")
        load_balancers = load_balancers_data.get("load_balancers", [])
        
        analysis = {
            "total_load_balancers": len(load_balancers),
            "total_monthly_cost": 0,
            "optimization_opportunities": []
        }
        
        for lb in load_balancers:
            monthly_cost = 12.00  # $12 per month for load balancer
            analysis["total_monthly_cost"] += monthly_cost
            
            # Check for load balancers with no droplets
            droplet_ids = lb.get("droplet_ids", [])
            if not droplet_ids:
                analysis["optimization_opportunities"].append({
                    "type": "empty_load_balancer",
                    "load_balancer_id": lb["id"],
                    "name": lb["name"],
                    "monthly_savings": monthly_cost,
                    "action": "Delete load balancer with no droplets"
                })
        
        return analysis
    
    def get_cost_summary(self) -> Dict:
        """Get comprehensive cost summary"""
        droplets_analysis = self.analyze_droplets()
        volumes_analysis = self.analyze_volumes()
        databases_analysis = self.analyze_databases()
        load_balancers_analysis = self.analyze_load_balancers()
        
        total_monthly_cost = (
            droplets_analysis["total_monthly_cost"] +
            volumes_analysis["total_size_gb"] * 0.10 +
            databases_analysis["total_monthly_cost"] +
            load_balancers_analysis["total_monthly_cost"]
        )
        
        total_potential_savings = sum(
            opp["monthly_savings"] for opp in droplets_analysis["optimization_opportunities"] +
            volumes_analysis["optimization_opportunities"] +
            databases_analysis["optimization_opportunities"] +
            load_balancers_analysis["optimization_opportunities"]
        )
        
        return {
            "current_monthly_cost": total_monthly_cost,
            "potential_monthly_savings": total_potential_savings,
            "savings_percentage": (total_potential_savings / total_monthly_cost * 100) if total_monthly_cost > 0 else 0,
            "resource_breakdown": {
                "droplets": droplets_analysis,
                "volumes": volumes_analysis,
                "databases": databases_analysis,
                "load_balancers": load_balancers_analysis
            },
            "all_optimization_opportunities": (
                droplets_analysis["optimization_opportunities"] +
                volumes_analysis["optimization_opportunities"] +
                databases_analysis["optimization_opportunities"] +
                load_balancers_analysis["optimization_opportunities"]
            )
        }
    
    def generate_optimization_report(self) -> str:
        """Generate a comprehensive optimization report"""
        cost_summary = self.get_cost_summary()
        
        report = f"""
Digital Ocean Cost Optimization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CURRENT COSTS:
- Total Monthly Cost: ${cost_summary['current_monthly_cost']:.2f}
- Droplets: ${cost_summary['resource_breakdown']['droplets']['total_monthly_cost']:.2f}
- Volumes: ${cost_summary['resource_breakdown']['volumes']['total_size_gb'] * 0.10:.2f}
- Databases: ${cost_summary['resource_breakdown']['databases']['total_monthly_cost']:.2f}
- Load Balancers: ${cost_summary['resource_breakdown']['load_balancers']['total_monthly_cost']:.2f}

OPTIMIZATION OPPORTUNITIES:
- Potential Monthly Savings: ${cost_summary['potential_monthly_savings']:.2f}
- Savings Percentage: {cost_summary['savings_percentage']:.1f}%

DETAILED RECOMMENDATIONS:
"""
        
        for i, opportunity in enumerate(cost_summary['all_optimization_opportunities'], 1):
            report += f"""
{i}. {opportunity['action']}
   - Resource: {opportunity.get('name', 'N/A')}
   - Type: {opportunity['type']}
   - Monthly Savings: ${opportunity['monthly_savings']:.2f}
"""
        
        return report
    
    def _get_droplet_monthly_cost(self, size_slug: str) -> float:
        """Get monthly cost for a droplet size"""
        # Simplified pricing - in production, you'd fetch from DO API
        pricing = {
            "s-1vcpu-1gb": 5.00,
            "s-1vcpu-2gb": 10.00,
            "s-2vcpu-2gb": 15.00,
            "s-2vcpu-4gb": 20.00,
            "s-4vcpu-8gb": 40.00,
            "s-6vcpu-16gb": 80.00,
            "s-8vcpu-32gb": 160.00,
            "s-12vcpu-48gb": 240.00,
            "s-16vcpu-64gb": 320.00,
            "s-20vcpu-96gb": 480.00,
            "s-24vcpu-128gb": 640.00,
            "s-32vcpu-192gb": 960.00
        }
        return pricing.get(size_slug, 0.0)
    
    def _get_database_monthly_cost(self, size_slug: str) -> float:
        """Get monthly cost for a database size"""
        # Simplified pricing
        pricing = {
            "db-s-1vcpu-1gb": 15.00,
            "db-s-1vcpu-2gb": 30.00,
            "db-s-2vcpu-4gb": 60.00,
            "db-s-4vcpu-8gb": 120.00,
            "db-s-6vcpu-16gb": 240.00,
            "db-s-8vcpu-32gb": 480.00
        }
        return pricing.get(size_slug, 0.0)
    
    def _is_droplet_oversized(self, droplet: Dict) -> bool:
        """Check if a droplet is oversized based on usage patterns"""
        # This would require monitoring data in production
        # For now, we'll use a simple heuristic
        size_slug = droplet.get("size_slug", "")
        return "s-8vcpu" in size_slug or "s-12vcpu" in size_slug or "s-16vcpu" in size_slug
    
    def _get_recommended_size(self, current_size: str) -> str:
        """Get recommended size for downsizing"""
        size_mapping = {
            "s-8vcpu-32gb": "s-4vcpu-8gb",
            "s-12vcpu-48gb": "s-6vcpu-16gb",
            "s-16vcpu-64gb": "s-8vcpu-32gb",
            "s-20vcpu-96gb": "s-12vcpu-48gb",
            "s-24vcpu-128gb": "s-16vcpu-64gb",
            "s-32vcpu-192gb": "s-20vcpu-96gb"
        }
        return size_mapping.get(current_size, current_size)

def main():
    """Main function to run Digital Ocean cost optimization analysis"""
    api_token = os.getenv('DIGITALOCEAN_API_TOKEN')
    if not api_token:
        print("Please set DIGITALOCEAN_API_TOKEN environment variable")
        return
    
    optimizer = DigitalOceanOptimizer(api_token)
    
    print("Digital Ocean Cost Optimization Analysis")
    print("=" * 50)
    
    # Generate and print the optimization report
    report = optimizer.generate_optimization_report()
    print(report)
    
    # Get detailed cost summary
    cost_summary = optimizer.get_cost_summary()
    
    print("\nQuick Actions:")
    print("=" * 50)
    print(f"1. Delete stopped droplets: Save ${sum(opp['monthly_savings'] for opp in cost_summary['all_optimization_opportunities'] if opp['type'] == 'stopped_droplet'):.2f}/month")
    print(f"2. Delete unattached volumes: Save ${sum(opp['monthly_savings'] for opp in cost_summary['all_optimization_opportunities'] if opp['type'] == 'unattached_volume'):.2f}/month")
    print(f"3. Downsize oversized droplets: Save ${sum(opp['monthly_savings'] for opp in cost_summary['all_optimization_opportunities'] if opp['type'] == 'oversized_droplet'):.2f}/month")

if __name__ == "__main__":
    main()
