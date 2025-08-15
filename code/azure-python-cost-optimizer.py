#!/usr/bin/env python3
"""
Azure Comprehensive Cost Optimizer
Analyzes Azure resources and provides optimization recommendations
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.sql import SqlManagementClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.containerinstance import ContainerInstanceManagementClient

class AzureCostOptimizer:
    def __init__(self, subscription_id: str):
        self.subscription_id = subscription_id
        self.credential = DefaultAzureCredential()
        
        # Initialize clients
        self.compute_client = ComputeManagementClient(self.credential, subscription_id)
        self.storage_client = StorageManagementClient(self.credential, subscription_id)
        self.sql_client = SqlManagementClient(self.credential, subscription_id)
        self.cost_client = CostManagementClient(self.credential, subscription_id)
        self.resource_client = ResourceManagementClient(self.credential, subscription_id)
        self.network_client = NetworkManagementClient(self.credential, subscription_id)
        self.container_client = ContainerInstanceManagementClient(self.credential, subscription_id)
        
    def analyze_virtual_machines(self) -> Dict:
        """Analyze virtual machines for optimization opportunities"""
        try:
            # Get all VMs across all resource groups
            vms = []
            resource_groups = self.resource_client.resource_groups.list()
            
            for rg in resource_groups:
                try:
                    vm_list = self.compute_client.virtual_machines.list(rg.name)
                    for vm in vm_list:
                        vm_data = {
                            'name': vm.name,
                            'resource_group': rg.name,
                            'location': vm.location,
                            'vm_size': vm.hardware_profile.vm_size,
                            'os_type': vm.storage_profile.os_disk.os_type.value if vm.storage_profile.os_disk.os_type else 'Unknown',
                            'power_state': self._get_vm_power_state(rg.name, vm.name),
                            'tags': vm.tags or {},
                            'created_time': vm.tags.get('created_time', 'Unknown') if vm.tags else 'Unknown'
                        }
                        vms.append(vm_data)
                except Exception as e:
                    print(f"Error getting VMs from resource group {rg.name}: {e}")
            
            analysis = {
                'total_vms': len(vms),
                'running_vms': len([vm for vm in vms if vm['power_state'] == 'VM running']),
                'stopped_vms': len([vm for vm in vms if vm['power_state'] == 'VM deallocated']),
                'vms': vms,
                'optimization_opportunities': []
            }
            
            # Identify optimization opportunities
            for vm in vms:
                if vm['power_state'] == 'VM deallocated':
                    analysis['optimization_opportunities'].append({
                        'type': 'stopped_vm',
                        'vm_name': vm['name'],
                        'resource_group': vm['resource_group'],
                        'action': 'Delete stopped VM',
                        'potential_savings': self._estimate_vm_cost(vm['vm_size'])
                    })
                
                elif vm['power_state'] == 'VM running':
                    # Check for oversized VMs
                    if self._is_vm_oversized(vm['vm_size']):
                        analysis['optimization_opportunities'].append({
                            'type': 'oversized_vm',
                            'vm_name': vm['name'],
                            'resource_group': vm['resource_group'],
                            'current_size': vm['vm_size'],
                            'recommended_size': self._get_recommended_vm_size(vm['vm_size']),
                            'action': 'Downsize VM',
                            'potential_savings': self._estimate_downsizing_savings(vm['vm_size'])
                        })
            
            return analysis
            
        except Exception as e:
            return {'error': f'VM analysis failed: {e}'}
    
    def analyze_storage_accounts(self) -> Dict:
        """Analyze storage accounts for optimization opportunities"""
        try:
            storage_accounts = self.storage_client.storage_accounts.list()
            
            analysis = {
                'total_accounts': 0,
                'accounts': [],
                'optimization_opportunities': []
            }
            
            for account in storage_accounts:
                try:
                    account_data = {
                        'name': account.name,
                        'resource_group': account.id.split('/')[4],
                        'location': account.location,
                        'sku': account.sku.name.value,
                        'kind': account.kind.value,
                        'access_tier': account.access_tier.value if account.access_tier else 'Unknown',
                        'created_time': account.creation_time
                    }
                    
                    analysis['accounts'].append(account_data)
                    analysis['total_accounts'] += 1
                    
                    # Check for optimization opportunities
                    if account.sku.name.value == 'Standard_LRS':
                        analysis['optimization_opportunities'].append({
                            'type': 'standard_storage',
                            'account_name': account.name,
                            'action': 'Consider moving to Premium or Cool storage tier',
                            'potential_savings': 'Medium'
                        })
                    
                    # Check for unused accounts (simplified check)
                    if account.creation_time < datetime.now() - timedelta(days=90):
                        analysis['optimization_opportunities'].append({
                            'type': 'old_storage_account',
                            'account_name': account.name,
                            'action': 'Review for deletion if unused',
                            'potential_savings': 'Low to Medium'
                        })
                
                except Exception as e:
                    print(f"Error analyzing storage account {account.name}: {e}")
            
            return analysis
            
        except Exception as e:
            return {'error': f'Storage account analysis failed: {e}'}
    
    def analyze_sql_databases(self) -> Dict:
        """Analyze SQL databases for optimization opportunities"""
        try:
            # Get all SQL servers
            servers = self.sql_client.servers.list()
            
            analysis = {
                'total_databases': 0,
                'databases': [],
                'optimization_opportunities': []
            }
            
            for server in servers:
                try:
                    # Get databases for this server
                    databases = self.sql_client.databases.list_by_server(
                        server.resource_group_name,
                        server.name
                    )
                    
                    for db in databases:
                        db_data = {
                            'name': db.name,
                            'server_name': server.name,
                            'resource_group': server.resource_group_name,
                            'location': server.location,
                            'sku': db.sku.name if db.sku else 'Unknown',
                            'tier': db.sku.tier if db.sku else 'Unknown',
                            'capacity': db.sku.capacity if db.sku else 0,
                            'status': db.status,
                            'created_date': db.creation_date
                        }
                        
                        analysis['databases'].append(db_data)
                        analysis['total_databases'] += 1
                        
                        # Check for optimization opportunities
                        if db.sku and db.sku.tier == 'Premium':
                            analysis['optimization_opportunities'].append({
                                'type': 'premium_database',
                                'database_name': db.name,
                                'server_name': server.name,
                                'action': 'Consider downgrading to Standard tier',
                                'potential_savings': 'High'
                            })
                        
                        if db.sku and db.sku.capacity > 100:  # DTUs > 100
                            analysis['optimization_opportunities'].append({
                                'type': 'oversized_database',
                                'database_name': db.name,
                                'server_name': server.name,
                                'current_capacity': db.sku.capacity,
                                'action': 'Right-size database capacity',
                                'potential_savings': 'Medium'
                            })
                
                except Exception as e:
                    print(f"Error analyzing SQL server {server.name}: {e}")
            
            return analysis
            
        except Exception as e:
            return {'error': f'SQL database analysis failed: {e}'}
    
    def analyze_network_resources(self) -> Dict:
        """Analyze network resources for optimization opportunities"""
        try:
            analysis = {
                'public_ips': [],
                'load_balancers': [],
                'network_interfaces': [],
                'optimization_opportunities': []
            }
            
            # Get public IPs
            resource_groups = self.resource_client.resource_groups.list()
            for rg in resource_groups:
                try:
                    public_ips = self.network_client.public_ip_addresses.list(rg.name)
                    for ip in public_ips:
                        ip_data = {
                            'name': ip.name,
                            'resource_group': rg.name,
                            'ip_address': ip.ip_address,
                            'allocation_method': ip.public_ip_allocation_method.value,
                            'sku': ip.sku.name.value if ip.sku else 'Basic',
                            'tags': ip.tags or {}
                        }
                        analysis['public_ips'].append(ip_data)
                        
                        # Check for unused public IPs
                        if not ip.ip_configuration:
                            analysis['optimization_opportunities'].append({
                                'type': 'unused_public_ip',
                                'resource_name': ip.name,
                                'resource_group': rg.name,
                                'action': 'Delete unused public IP',
                                'potential_savings': 'Low'
                            })
                
                except Exception as e:
                    print(f"Error analyzing network resources in {rg.name}: {e}")
            
            return analysis
            
        except Exception as e:
            return {'error': f'Network resource analysis failed: {e}'}
    
    def analyze_container_instances(self) -> Dict:
        """Analyze container instances for optimization opportunities"""
        try:
            container_groups = self.container_client.container_groups.list()
            
            analysis = {
                'total_groups': 0,
                'groups': [],
                'optimization_opportunities': []
            }
            
            for group in container_groups:
                group_data = {
                    'name': group.name,
                    'resource_group': group.id.split('/')[4],
                    'location': group.location,
                    'os_type': group.os_type.value,
                    'restart_policy': group.restart_policy.value,
                    'state': group.instance_view.state if group.instance_view else 'Unknown',
                    'containers': len(group.containers)
                }
                
                analysis['groups'].append(group_data)
                analysis['total_groups'] += 1
                
                # Check for optimization opportunities
                if group.restart_policy.value == 'Always':
                    analysis['optimization_opportunities'].append({
                        'type': 'always_restart_container',
                        'group_name': group.name,
                        'action': 'Consider using OnFailure restart policy',
                        'potential_savings': 'Low'
                    })
            
            return analysis
            
        except Exception as e:
            return {'error': f'Container instance analysis failed: {e}'}
    
    def get_cost_data(self, start_date: str, end_date: str) -> Dict:
        """Get cost data for the specified period"""
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
            
            result = self.cost_client.query.usage(
                scope=f"/subscriptions/{self.subscription_id}",
                parameters=query
            )
            
            costs = {
                'period': f"{start_date} to {end_date}",
                'total_cost': 0,
                'cost_by_service': {},
                'cost_by_region': {},
                'note': 'Cost data processing would be implemented based on result structure'
            }
            
            return costs
            
        except Exception as e:
            return {'error': f'Cost data retrieval failed: {e}'}
    
    def generate_optimization_report(self) -> str:
        """Generate comprehensive optimization report"""
        # Run all analyses
        vm_analysis = self.analyze_virtual_machines()
        storage_analysis = self.analyze_storage_accounts()
        sql_analysis = self.analyze_sql_databases()
        network_analysis = self.analyze_network_resources()
        container_analysis = self.analyze_container_instances()
        
        # Get cost data for last month
        end_date = datetime.now().replace(day=1) - timedelta(days=1)
        start_date = end_date.replace(day=1)
        cost_data = self.get_cost_data(
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d')
        )
        
        report = f"""
Azure Cost Optimization Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Subscription: {self.subscription_id}

COST SUMMARY:
- Total Cost (Last Month): ${cost_data.get('total_cost', 0):.2f}

RESOURCE ANALYSIS:
- Virtual Machines: {vm_analysis.get('total_vms', 0)} total ({vm_analysis.get('running_vms', 0)} running)
- Storage Accounts: {storage_analysis.get('total_accounts', 0)} total
- SQL Databases: {sql_analysis.get('total_databases', 0)} total
- Container Groups: {container_analysis.get('total_groups', 0)} total

OPTIMIZATION OPPORTUNITIES:
"""
        
        # Combine all optimization opportunities
        all_opportunities = []
        all_opportunities.extend(vm_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(storage_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(sql_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(network_analysis.get('optimization_opportunities', []))
        all_opportunities.extend(container_analysis.get('optimization_opportunities', []))
        
        for i, opportunity in enumerate(all_opportunities, 1):
            report += f"""
{i}. {opportunity['action']}
   - Type: {opportunity['type']}
   - Resource: {opportunity.get('vm_name', opportunity.get('account_name', opportunity.get('database_name', opportunity.get('resource_name', opportunity.get('group_name', 'N/A')))))}
   - Resource Group: {opportunity.get('resource_group', 'N/A')}
   - Potential Savings: {opportunity.get('potential_savings', 'N/A')}
"""
        
        return report
    
    def _get_vm_power_state(self, resource_group: str, vm_name: str) -> str:
        """Get the power state of a VM"""
        try:
            vm_instance_view = self.compute_client.virtual_machines.instance_view(resource_group, vm_name)
            for status in vm_instance_view.statuses:
                if status.code.startswith('PowerState/'):
                    return status.display_status
            return 'Unknown'
        except Exception:
            return 'Unknown'
    
    def _estimate_vm_cost(self, vm_size: str) -> str:
        """Estimate monthly cost for a VM size"""
        # Simplified pricing - in production, you'd fetch from Azure Pricing API
        pricing = {
            'Standard_B1s': 8.76,
            'Standard_B2s': 17.52,
            'Standard_D2s_v3': 70.08,
            'Standard_D4s_v3': 140.16,
            'Standard_E2s_v3': 70.08,
            'Standard_E4s_v3': 140.16
        }
        return f"${pricing.get(vm_size, 50.0):.2f}/month"
    
    def _is_vm_oversized(self, vm_size: str) -> bool:
        """Check if VM size is oversized"""
        oversized_sizes = ['Standard_D8s_v3', 'Standard_D16s_v3', 'Standard_E8s_v3', 'Standard_E16s_v3']
        return vm_size in oversized_sizes
    
    def _get_recommended_vm_size(self, current_size: str) -> str:
        """Get recommended VM size for downsizing"""
        recommendations = {
            'Standard_D8s_v3': 'Standard_D4s_v3',
            'Standard_D16s_v3': 'Standard_D8s_v3',
            'Standard_E8s_v3': 'Standard_E4s_v3',
            'Standard_E16s_v3': 'Standard_E8s_v3'
        }
        return recommendations.get(current_size, current_size)
    
    def _estimate_downsizing_savings(self, vm_size: str) -> str:
        """Estimate savings from downsizing"""
        return "30-50% of current cost"

def main():
    """Main function to run Azure cost optimization analysis"""
    subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
    if not subscription_id:
        print("Please set AZURE_SUBSCRIPTION_ID environment variable")
        return
    
    optimizer = AzureCostOptimizer(subscription_id)
    
    print("Azure Cost Optimization Analysis")
    print("=" * 40)
    
    # Generate and print the optimization report
    report = optimizer.generate_optimization_report()
    print(report)
    
    # Save detailed analysis to JSON
    detailed_analysis = {
        'virtual_machines': optimizer.analyze_virtual_machines(),
        'storage_accounts': optimizer.analyze_storage_accounts(),
        'sql_databases': optimizer.analyze_sql_databases(),
        'network_resources': optimizer.analyze_network_resources(),
        'container_instances': optimizer.analyze_container_instances()
    }
    
    with open('azure_optimization_analysis.json', 'w') as f:
        json.dump(detailed_analysis, f, indent=2, default=str)
    
    print(f"\nDetailed analysis saved to azure_optimization_analysis.json")

if __name__ == "__main__":
    main()
