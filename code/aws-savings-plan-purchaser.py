#!/usr/bin/env python3
"""
AWS Savings Plan Automated Purchaser
Analyzes usage patterns and automatically purchases optimal Savings Plans
"""

import os
import boto3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import pandas as pd

class SavingsPlanOptimizer:
    def __init__(self, region: str = 'us-east-1'):
        self.region = region
        self.ce_client = boto3.client('ce', region_name=region)
        self.savings_plans_client = boto3.client('savingsplans', region_name=region)
        self.ec2_client = boto3.client('ec2', region_name=region)
        self.fargate_client = boto3.client('ecs', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        
    def analyze_usage_patterns(self, days: int = 90) -> Dict:
        """Analyze usage patterns to determine optimal Savings Plan purchases"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Get cost and usage data
            response = self.ce_client.get_cost_and_usage(
                TimePeriod={
                    'Start': start_date.strftime('%Y-%m-%d'),
                    'End': end_date.strftime('%Y-%m-%d')
                },
                Granularity='MONTHLY',
                Metrics=['UnblendedCost', 'UsageQuantity'],
                GroupBy=[
                    {'Type': 'DIMENSION', 'Key': 'SERVICE'},
                    {'Type': 'DIMENSION', 'Key': 'USAGE_TYPE'},
                    {'Type': 'DIMENSION', 'Key': 'REGION'}
                ]
            )
            
            # Process usage data
            usage_data = self._process_usage_data(response)
            
            # Analyze patterns
            patterns = {
                'total_cost': 0,
                'eligible_services': {},
                'usage_by_region': {},
                'usage_by_month': {},
                'recommendations': []
            }
            
            for result in response['ResultsByTime']:
                for group in result['Groups']:
                    keys = group['Keys']
                    service = keys[0]
                    usage_type = keys[1]
                    region = keys[2]
                    cost = float(group['Metrics']['UnblendedCost']['Amount'])
                    usage = float(group['Metrics']['UsageQuantity']['Amount'])
                    
                    patterns['total_cost'] += cost
                    
                    # Track eligible services (EC2, Fargate, Lambda)
                    if service in ['Amazon Elastic Compute Cloud', 'Amazon Elastic Container Service', 'AWS Lambda']:
                        if service not in patterns['eligible_services']:
                            patterns['eligible_services'][service] = 0
                        patterns['eligible_services'][service] += cost
                    
                    # Track usage by region
                    if region not in patterns['usage_by_region']:
                        patterns['usage_by_region'][region] = 0
                    patterns['usage_by_region'][region] += cost
            
            # Generate recommendations
            patterns['recommendations'] = self._generate_savings_plan_recommendations(patterns)
            
            return patterns
            
        except Exception as e:
            return {'error': f'Usage pattern analysis failed: {e}'}
    
    def _process_usage_data(self, response: Dict) -> Dict:
        """Process raw usage data from Cost Explorer"""
        processed_data = {
            'services': {},
            'regions': {},
            'usage_types': {}
        }
        
        for result in response['ResultsByTime']:
            for group in result['Groups']:
                keys = group['Keys']
                service = keys[0]
                usage_type = keys[1]
                region = keys[2]
                cost = float(group['Metrics']['UnblendedCost']['Amount'])
                usage = float(group['Metrics']['UsageQuantity']['Amount'])
                
                # Aggregate by service
                if service not in processed_data['services']:
                    processed_data['services'][service] = {'cost': 0, 'usage': 0}
                processed_data['services'][service]['cost'] += cost
                processed_data['services'][service]['usage'] += usage
                
                # Aggregate by region
                if region not in processed_data['regions']:
                    processed_data['regions'][region] = {'cost': 0, 'usage': 0}
                processed_data['regions'][region]['cost'] += cost
                processed_data['regions'][region]['usage'] += usage
                
                # Aggregate by usage type
                if usage_type not in processed_data['usage_types']:
                    processed_data['usage_types'][usage_type] = {'cost': 0, 'usage': 0}
                processed_data['usage_types'][usage_type]['cost'] += cost
                processed_data['usage_types'][usage_type]['usage'] += usage
        
        return processed_data
    
    def _generate_savings_plan_recommendations(self, patterns: Dict) -> List[Dict]:
        """Generate Savings Plan purchase recommendations"""
        recommendations = []
        
        # Calculate eligible spend
        eligible_spend = sum(patterns['eligible_services'].values())
        total_spend = patterns['total_cost']
        
        if eligible_spend > 0:
            # EC2 Compute Savings Plans
            ec2_spend = patterns['eligible_services'].get('Amazon Elastic Compute Cloud', 0)
            if ec2_spend > 100:  # Minimum $100/month for recommendation
                recommendations.append({
                    'type': 'EC2 Compute Savings Plans',
                    'eligible_spend': ec2_spend,
                    'recommended_commitment': self._calculate_commitment(ec2_spend, 0.7),  # 70% commitment
                    'savings_rate': 'Up to 72%',
                    'term': '1 year',
                    'estimated_savings': ec2_spend * 0.3,  # 30% average savings
                    'priority': 'high' if ec2_spend > 500 else 'medium'
                })
            
            # Fargate Compute Savings Plans
            fargate_spend = patterns['eligible_services'].get('Amazon Elastic Container Service', 0)
            if fargate_spend > 50:  # Minimum $50/month for recommendation
                recommendations.append({
                    'type': 'Fargate Compute Savings Plans',
                    'eligible_spend': fargate_spend,
                    'recommended_commitment': self._calculate_commitment(fargate_spend, 0.6),  # 60% commitment
                    'savings_rate': 'Up to 50%',
                    'term': '1 year',
                    'estimated_savings': fargate_spend * 0.25,  # 25% average savings
                    'priority': 'medium'
                })
            
            # Lambda Compute Savings Plans
            lambda_spend = patterns['eligible_services'].get('AWS Lambda', 0)
            if lambda_spend > 30:  # Minimum $30/month for recommendation
                recommendations.append({
                    'type': 'Lambda Compute Savings Plans',
                    'eligible_spend': lambda_spend,
                    'recommended_commitment': self._calculate_commitment(lambda_spend, 0.5),  # 50% commitment
                    'savings_rate': 'Up to 17%',
                    'term': '1 year',
                    'estimated_savings': lambda_spend * 0.1,  # 10% average savings
                    'priority': 'low'
                })
        
        return recommendations
    
    def _calculate_commitment(self, monthly_spend: float, commitment_percentage: float) -> float:
        """Calculate recommended monthly commitment amount"""
        return monthly_spend * commitment_percentage
    
    def get_current_savings_plans(self) -> Dict:
        """Get current Savings Plans"""
        try:
            response = self.savings_plans_client.describe_savings_plans(
                states=['ACTIVE']
            )
            
            current_plans = {
                'total_plans': len(response['savingsPlans']),
                'plans': [],
                'total_commitment': 0,
                'total_savings': 0
            }
            
            for plan in response['savingsPlans']:
                plan_data = {
                    'plan_id': plan['savingsPlanId'],
                    'type': plan['savingsPlanType'],
                    'state': plan['state'],
                    'commitment': plan['commitment'],
                    'start': plan['start'],
                    'end': plan['end'],
                    'hourly_commitment': plan['hourlyCommitmentToSpend'],
                    'upfront_amount': plan.get('upfrontPaymentAmount', 0),
                    'monthly_payment': plan.get('monthlyPaymentAmount', 0)
                }
                
                current_plans['plans'].append(plan_data)
                current_plans['total_commitment'] += float(plan['commitment'])
            
            return current_plans
            
        except Exception as e:
            return {'error': f'Failed to get current Savings Plans: {e}'}
    
    def calculate_optimal_purchase(self, target_savings_percentage: float = 0.3) -> Dict:
        """Calculate optimal Savings Plan purchase to achieve target savings"""
        try:
            # Analyze usage patterns
            usage_patterns = self.analyze_usage_patterns()
            
            if 'error' in usage_patterns:
                return usage_patterns
            
            # Get current plans
            current_plans = self.get_current_savings_plans()
            
            # Calculate optimal purchase
            total_eligible_spend = sum(usage_patterns['eligible_services'].values())
            current_commitment = current_plans.get('total_commitment', 0)
            
            # Calculate additional commitment needed
            target_commitment = total_eligible_spend * target_savings_percentage
            additional_commitment = max(0, target_commitment - current_commitment)
            
            optimal_purchase = {
                'current_eligible_spend': total_eligible_spend,
                'current_commitment': current_commitment,
                'target_savings_percentage': target_savings_percentage,
                'target_commitment': target_commitment,
                'additional_commitment_needed': additional_commitment,
                'estimated_monthly_savings': additional_commitment * 0.3,  # 30% average savings
                'recommended_purchases': []
            }
            
            # Break down by service type
            for service, spend in usage_patterns['eligible_services'].items():
                if spend > 50:  # Minimum threshold
                    service_commitment = spend * target_savings_percentage
                    optimal_purchase['recommended_purchases'].append({
                        'service': service,
                        'monthly_spend': spend,
                        'recommended_commitment': service_commitment,
                        'savings_plan_type': self._get_savings_plan_type(service),
                        'estimated_savings': service_commitment * 0.3
                    })
            
            return optimal_purchase
            
        except Exception as e:
            return {'error': f'Optimal purchase calculation failed: {e}'}
    
    def _get_savings_plan_type(self, service: str) -> str:
        """Get appropriate Savings Plan type for service"""
        if service == 'Amazon Elastic Compute Cloud':
            return 'EC2 Compute Savings Plans'
        elif service == 'Amazon Elastic Container Service':
            return 'Fargate Compute Savings Plans'
        elif service == 'AWS Lambda':
            return 'Lambda Compute Savings Plans'
        else:
            return 'Compute Savings Plans'
    
    def simulate_savings_plan_purchase(self, commitment_amount: float, 
                                     plan_type: str = 'EC2 Compute Savings Plans',
                                     term: str = '1 year') -> Dict:
        """Simulate a Savings Plan purchase to estimate savings"""
        try:
            # Get current usage patterns
            usage_patterns = self.analyze_usage_patterns()
            
            if 'error' in usage_patterns:
                return usage_patterns
            
            # Calculate savings based on plan type
            savings_rate = self._get_savings_rate(plan_type)
            eligible_spend = self._get_eligible_spend_for_plan(usage_patterns, plan_type)
            
            # Calculate savings
            monthly_commitment = commitment_amount / 12  # Convert annual to monthly
            covered_spend = min(monthly_commitment, eligible_spend)
            uncovered_spend = max(0, eligible_spend - monthly_commitment)
            
            monthly_savings = covered_spend * savings_rate
            annual_savings = monthly_savings * 12
            total_cost = commitment_amount
            net_savings = annual_savings - total_cost
            
            simulation = {
                'plan_type': plan_type,
                'term': term,
                'commitment_amount': commitment_amount,
                'monthly_commitment': monthly_commitment,
                'eligible_monthly_spend': eligible_spend,
                'covered_spend': covered_spend,
                'uncovered_spend': uncovered_spend,
                'savings_rate': savings_rate,
                'monthly_savings': monthly_savings,
                'annual_savings': annual_savings,
                'total_cost': total_cost,
                'net_savings': net_savings,
                'roi_percentage': (net_savings / total_cost * 100) if total_cost > 0 else 0,
                'payback_period_months': total_cost / monthly_savings if monthly_savings > 0 else float('inf')
            }
            
            return simulation
            
        except Exception as e:
            return {'error': f'Savings Plan simulation failed: {e}'}
    
    def _get_savings_rate(self, plan_type: str) -> float:
        """Get savings rate for plan type"""
        rates = {
            'EC2 Compute Savings Plans': 0.3,  # 30% average
            'Fargate Compute Savings Plans': 0.25,  # 25% average
            'Lambda Compute Savings Plans': 0.1,  # 10% average
            'Compute Savings Plans': 0.3  # Default
        }
        return rates.get(plan_type, 0.2)
    
    def _get_eligible_spend_for_plan(self, usage_patterns: Dict, plan_type: str) -> float:
        """Get eligible spend for specific plan type"""
        if plan_type == 'EC2 Compute Savings Plans':
            return usage_patterns['eligible_services'].get('Amazon Elastic Compute Cloud', 0)
        elif plan_type == 'Fargate Compute Savings Plans':
            return usage_patterns['eligible_services'].get('Amazon Elastic Container Service', 0)
        elif plan_type == 'Lambda Compute Savings Plans':
            return usage_patterns['eligible_services'].get('AWS Lambda', 0)
        else:
            return sum(usage_patterns['eligible_services'].values())
    
    def generate_savings_plan_report(self) -> str:
        """Generate comprehensive Savings Plan analysis report"""
        try:
            # Get usage patterns
            usage_patterns = self.analyze_usage_patterns()
            current_plans = self.get_current_savings_plans()
            optimal_purchase = self.calculate_optimal_purchase()
            
            report = f"""
AWS Savings Plan Analysis Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CURRENT USAGE ANALYSIS:
- Total Spend (Last 90 Days): ${usage_patterns.get('total_cost', 0):.2f}
- Eligible Services Spend: ${sum(usage_patterns.get('eligible_services', {}).values()):.2f}

CURRENT SAVINGS PLANS:
- Active Plans: {current_plans.get('total_plans', 0)}
- Total Commitment: ${current_plans.get('total_commitment', 0):.2f}

RECOMMENDATIONS:
"""
            
            for i, rec in enumerate(usage_patterns.get('recommendations', []), 1):
                report += f"""
{i}. {rec['type']}
   - Eligible Spend: ${rec['eligible_spend']:.2f}/month
   - Recommended Commitment: ${rec['recommended_commitment']:.2f}/month
   - Estimated Savings: ${rec['estimated_savings']:.2f}/month
   - Savings Rate: {rec['savings_rate']}
   - Priority: {rec['priority'].upper()}
"""
            
            if optimal_purchase.get('additional_commitment_needed', 0) > 0:
                report += f"""
OPTIMAL PURCHASE STRATEGY:
- Additional Commitment Needed: ${optimal_purchase['additional_commitment_needed']:.2f}
- Estimated Monthly Savings: ${optimal_purchase['estimated_monthly_savings']:.2f}
- Target Savings Percentage: {optimal_purchase['target_savings_percentage']*100:.1f}%

DETAILED PURCHASE RECOMMENDATIONS:
"""
                
                for purchase in optimal_purchase.get('recommended_purchases', []):
                    report += f"""
• {purchase['service']}
  - Monthly Spend: ${purchase['monthly_spend']:.2f}
  - Recommended Commitment: ${purchase['recommended_commitment']:.2f}
  - Plan Type: {purchase['savings_plan_type']}
  - Estimated Savings: ${purchase['estimated_savings']:.2f}/month
"""
            
            return report
            
        except Exception as e:
            return f"Report generation failed: {e}"

def main():
    """Main function to run Savings Plan optimization analysis"""
    optimizer = SavingsPlanOptimizer()
    
    print("AWS Savings Plan Optimization Analysis")
    print("=" * 50)
    
    # Generate comprehensive report
    report = optimizer.generate_savings_plan_report()
    print(report)
    
    # Run simulation for EC2 Compute Savings Plans
    print("\n" + "=" * 50)
    print("SAVINGS PLAN SIMULATION")
    print("=" * 50)
    
    simulation = optimizer.simulate_savings_plan_purchase(
        commitment_amount=12000,  # $12,000 annual commitment
        plan_type='EC2 Compute Savings Plans',
        term='1 year'
    )
    
    if 'error' not in simulation:
        print(f"Plan Type: {simulation['plan_type']}")
        print(f"Annual Commitment: ${simulation['commitment_amount']:.2f}")
        print(f"Monthly Commitment: ${simulation['monthly_commitment']:.2f}")
        print(f"Eligible Monthly Spend: ${simulation['eligible_monthly_spend']:.2f}")
        print(f"Monthly Savings: ${simulation['monthly_savings']:.2f}")
        print(f"Annual Savings: ${simulation['annual_savings']:.2f}")
        print(f"Net Savings: ${simulation['net_savings']:.2f}")
        print(f"ROI: {simulation['roi_percentage']:.1f}%")
        print(f"Payback Period: {simulation['payback_period_months']:.1f} months")
    
    # Save detailed analysis
    detailed_analysis = {
        'usage_patterns': optimizer.analyze_usage_patterns(),
        'current_plans': optimizer.get_current_savings_plans(),
        'optimal_purchase': optimizer.calculate_optimal_purchase(),
        'simulation': simulation
    }
    
    with open('savings_plan_analysis.json', 'w') as f:
        json.dump(detailed_analysis, f, indent=2, default=str)
    
    print(f"\nDetailed analysis saved to savings_plan_analysis.json")

if __name__ == "__main__":
    main()
