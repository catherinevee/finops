#!/usr/bin/env python3
"""
Multi-Cloud Cost Anomaly Detector
Uses statistical methods and ML to detect cost anomalies across clouds
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class CostAnomalyDetector:
    def __init__(self, sensitivity: float = 0.1):
        self.sensitivity = sensitivity
        self.historical_data = {}
        self.anomaly_thresholds = {}
        self.isolation_forest = IsolationForest(
            contamination=sensitivity,
            random_state=42
        )
        self.scaler = StandardScaler()
    
    def load_historical_data(self, data_source: str, file_path: str = None):
        """Load historical cost data from various sources"""
        if data_source == "file" and file_path:
            try:
                with open(file_path, 'r') as f:
                    self.historical_data = json.load(f)
                print(f"✓ Loaded historical data from {file_path}")
            except Exception as e:
                print(f"✗ Failed to load data from file: {e}")
        
        elif data_source == "sample":
            # Generate sample data for demonstration
            self._generate_sample_data()
            print("✓ Generated sample historical data")
    
    def _generate_sample_data(self):
        """Generate sample historical cost data"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        
        dates = []
        aws_costs = []
        azure_costs = []
        gcp_costs = []
        do_costs = []
        
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date.strftime('%Y-%m-%d'))
            
            # Generate realistic cost patterns with some anomalies
            base_aws = 1000 + np.random.normal(0, 50)
            base_azure = 800 + np.random.normal(0, 40)
            base_gcp = 600 + np.random.normal(0, 30)
            base_do = 200 + np.random.normal(0, 10)
            
            # Add some anomalies
            if current_date.day == 15:  # Mid-month spike
                base_aws *= 1.5
                base_azure *= 1.3
            
            if current_date.day == 25:  # End-month spike
                base_gcp *= 1.4
                base_do *= 1.2
            
            # Add random anomalies
            if np.random.random() < 0.05:  # 5% chance of anomaly
                base_aws *= np.random.uniform(1.2, 2.0)
            
            aws_costs.append(max(0, base_aws))
            azure_costs.append(max(0, base_azure))
            gcp_costs.append(max(0, base_gcp))
            do_costs.append(max(0, base_do))
            
            current_date += timedelta(days=1)
        
        self.historical_data = {
            "dates": dates,
            "aws": aws_costs,
            "azure": azure_costs,
            "gcp": gcp_costs,
            "digitalocean": do_costs
        }
    
    def detect_statistical_anomalies(self, provider: str, window_days: int = 30) -> List[Dict]:
        """Detect anomalies using statistical methods (Z-score, IQR)"""
        if provider not in self.historical_data:
            return []
        
        costs = self.historical_data[provider]
        dates = self.historical_data["dates"]
        
        # Use rolling window for more accurate detection
        df = pd.DataFrame({
            'date': dates,
            'cost': costs
        })
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # Calculate rolling statistics
        df['rolling_mean'] = df['cost'].rolling(window=window_days, center=True).mean()
        df['rolling_std'] = df['cost'].rolling(window=window_days, center=True).std()
        df['z_score'] = (df['cost'] - df['rolling_mean']) / df['rolling_std']
        
        # Calculate IQR-based outliers
        Q1 = df['cost'].quantile(0.25)
        Q3 = df['cost'].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        anomalies = []
        
        for idx, row in df.iterrows():
            is_anomaly = False
            anomaly_type = ""
            severity = "low"
            
            # Z-score based detection
            if abs(row['z_score']) > 2.5:
                is_anomaly = True
                anomaly_type = "z_score"
                severity = "high" if abs(row['z_score']) > 3.5 else "medium"
            
            # IQR based detection
            elif row['cost'] < lower_bound or row['cost'] > upper_bound:
                is_anomaly = True
                anomaly_type = "iqr"
                severity = "high" if abs(row['cost'] - df['cost'].mean()) > 2 * df['cost'].std() else "medium"
            
            if is_anomaly:
                anomalies.append({
                    'date': row['date'].strftime('%Y-%m-%d'),
                    'cost': row['cost'],
                    'expected_cost': row['rolling_mean'],
                    'anomaly_type': anomaly_type,
                    'severity': severity,
                    'z_score': row['z_score'],
                    'deviation_percent': ((row['cost'] - row['rolling_mean']) / row['rolling_mean'] * 100) if row['rolling_mean'] > 0 else 0
                })
        
        return anomalies
    
    def detect_ml_anomalies(self, provider: str) -> List[Dict]:
        """Detect anomalies using Machine Learning (Isolation Forest)"""
        if provider not in self.historical_data:
            return []
        
        costs = np.array(self.historical_data[provider]).reshape(-1, 1)
        dates = self.historical_data["dates"]
        
        # Prepare features for ML
        features = self._extract_features(costs)
        
        # Fit the model
        self.isolation_forest.fit(features)
        
        # Predict anomalies
        predictions = self.isolation_forest.predict(features)
        anomaly_scores = self.isolation_forest.decision_function(features)
        
        anomalies = []
        for i, (prediction, score, cost, date) in enumerate(zip(predictions, anomaly_scores, costs, dates)):
            if prediction == -1:  # Anomaly detected
                severity = "high" if score < -0.5 else "medium" if score < -0.3 else "low"
                
                anomalies.append({
                    'date': date,
                    'cost': float(cost[0]),
                    'anomaly_score': float(score),
                    'anomaly_type': 'isolation_forest',
                    'severity': severity,
                    'deviation_percent': 0  # Would need historical mean for this
                })
        
        return anomalies
    
    def _extract_features(self, costs: np.ndarray) -> np.ndarray:
        """Extract features for ML anomaly detection"""
        features = []
        
        for i in range(len(costs)):
            feature_vector = []
            
            # Current cost
            feature_vector.append(costs[i][0])
            
            # Rolling statistics (if available)
            if i >= 7:
                feature_vector.append(np.mean(costs[i-7:i]))
                feature_vector.append(np.std(costs[i-7:i]))
            else:
                feature_vector.extend([costs[i][0], 0])
            
            if i >= 30:
                feature_vector.append(np.mean(costs[i-30:i]))
                feature_vector.append(np.std(costs[i-30:i]))
            else:
                feature_vector.extend([costs[i][0], 0])
            
            # Day of week pattern (if we have enough data)
            if i >= 7:
                feature_vector.append(costs[i-7][0])  # Same day last week
            else:
                feature_vector.append(costs[i][0])
            
            features.append(feature_vector)
        
        return np.array(features)
    
    def detect_trend_anomalies(self, provider: str, threshold_percent: float = 20) -> List[Dict]:
        """Detect anomalies based on trend analysis"""
        if provider not in self.historical_data:
            return []
        
        costs = self.historical_data[provider]
        dates = self.historical_data["dates"]
        
        anomalies = []
        
        for i in range(7, len(costs)):
            # Calculate moving average
            moving_avg = np.mean(costs[i-7:i])
            current_cost = costs[i]
            
            # Calculate percentage change
            if moving_avg > 0:
                percent_change = ((current_cost - moving_avg) / moving_avg) * 100
                
                if abs(percent_change) > threshold_percent:
                    severity = "high" if abs(percent_change) > 50 else "medium"
                    
                    anomalies.append({
                        'date': dates[i],
                        'cost': current_cost,
                        'expected_cost': moving_avg,
                        'anomaly_type': 'trend',
                        'severity': severity,
                        'deviation_percent': percent_change,
                        'trend_direction': 'increase' if percent_change > 0 else 'decrease'
                    })
        
        return anomalies
    
    def detect_seasonal_anomalies(self, provider: str) -> List[Dict]:
        """Detect anomalies based on seasonal patterns"""
        if provider not in self.historical_data:
            return []
        
        costs = self.historical_data[provider]
        dates = self.historical_data["dates"]
        
        # Convert to DataFrame for easier analysis
        df = pd.DataFrame({
            'date': pd.to_datetime(dates),
            'cost': costs
        })
        
        # Extract day of week and month
        df['day_of_week'] = df['date'].dt.dayofweek
        df['month'] = df['date'].dt.month
        df['day_of_month'] = df['date'].dt.day
        
        anomalies = []
        
        # Analyze day-of-week patterns
        for day in range(7):
            day_data = df[df['day_of_week'] == day]['cost']
            if len(day_data) > 0:
                day_mean = day_data.mean()
                day_std = day_data.std()
                
                # Find days that deviate significantly from the day-of-week pattern
                for idx, row in df[df['day_of_week'] == day].iterrows():
                    if day_std > 0:
                        z_score = abs((row['cost'] - day_mean) / day_std)
                        if z_score > 2.5:
                            severity = "high" if z_score > 3.5 else "medium"
                            anomalies.append({
                                'date': row['date'].strftime('%Y-%m-%d'),
                                'cost': row['cost'],
                                'expected_cost': day_mean,
                                'anomaly_type': 'seasonal',
                                'severity': severity,
                                'deviation_percent': ((row['cost'] - day_mean) / day_mean * 100) if day_mean > 0 else 0,
                                'pattern_type': f'day_of_week_{day}'
                            })
        
        return anomalies
    
    def comprehensive_anomaly_detection(self, provider: str) -> Dict:
        """Run all anomaly detection methods and combine results"""
        results = {
            'provider': provider,
            'total_anomalies': 0,
            'anomalies_by_type': {},
            'anomalies_by_severity': {'low': 0, 'medium': 0, 'high': 0},
            'all_anomalies': []
        }
        
        # Run different detection methods
        statistical_anomalies = self.detect_statistical_anomalies(provider)
        ml_anomalies = self.detect_ml_anomalies(provider)
        trend_anomalies = self.detect_trend_anomalies(provider)
        seasonal_anomalies = self.detect_seasonal_anomalies(provider)
        
        # Combine all anomalies
        all_anomalies = statistical_anomalies + ml_anomalies + trend_anomalies + seasonal_anomalies
        
        # Remove duplicates based on date
        unique_anomalies = {}
        for anomaly in all_anomalies:
            date = anomaly['date']
            if date not in unique_anomalies:
                unique_anomalies[date] = anomaly
            else:
                # Keep the one with higher severity
                existing = unique_anomalies[date]
                if self._get_severity_score(anomaly['severity']) > self._get_severity_score(existing['severity']):
                    unique_anomalies[date] = anomaly
        
        results['all_anomalies'] = list(unique_anomalies.values())
        results['total_anomalies'] = len(results['all_anomalies'])
        
        # Categorize by type and severity
        for anomaly in results['all_anomalies']:
            anomaly_type = anomaly['anomaly_type']
            severity = anomaly['severity']
            
            if anomaly_type not in results['anomalies_by_type']:
                results['anomalies_by_type'][anomaly_type] = 0
            results['anomalies_by_type'][anomaly_type] += 1
            
            results['anomalies_by_severity'][severity] += 1
        
        return results
    
    def _get_severity_score(self, severity: str) -> int:
        """Convert severity string to numeric score"""
        severity_scores = {'low': 1, 'medium': 2, 'high': 3}
        return severity_scores.get(severity, 0)
    
    def generate_anomaly_report(self, providers: List[str] = None) -> str:
        """Generate comprehensive anomaly detection report"""
        if providers is None:
            providers = list(self.historical_data.keys())
        
        report = f"""
Multi-Cloud Cost Anomaly Detection Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ANOMALY DETECTION RESULTS:
"""
        
        total_anomalies = 0
        high_severity_count = 0
        
        for provider in providers:
            if provider in self.historical_data:
                results = self.comprehensive_anomaly_detection(provider)
                
                report += f"\n{provider.upper()}:\n"
                report += f"- Total Anomalies: {results['total_anomalies']}\n"
                report += f"- High Severity: {results['anomalies_by_severity']['high']}\n"
                report += f"- Medium Severity: {results['anomalies_by_severity']['medium']}\n"
                report += f"- Low Severity: {results['anomalies_by_severity']['low']}\n"
                
                if results['anomalies_by_type']:
                    report += "- Detection Methods:\n"
                    for method, count in results['anomalies_by_type'].items():
                        report += f"  • {method}: {count}\n"
                
                total_anomalies += results['total_anomalies']
                high_severity_count += results['anomalies_by_severity']['high']
        
        report += f"\nSUMMARY:\n"
        report += f"- Total Anomalies Detected: {total_anomalies}\n"
        report += f"- High Severity Anomalies: {high_severity_count}\n"
        
        if high_severity_count > 0:
            report += f"\n⚠️  ALERT: {high_severity_count} high-severity anomalies detected!\n"
            report += "Immediate investigation recommended.\n"
        
        return report

def main():
    """Main function to run cost anomaly detection"""
    detector = CostAnomalyDetector(sensitivity=0.1)
    
    print("Multi-Cloud Cost Anomaly Detection")
    print("=" * 50)
    
    # Load sample data
    detector.load_historical_data("sample")
    
    # Run anomaly detection for all providers
    providers = ['aws', 'azure', 'gcp', 'digitalocean']
    
    # Generate comprehensive report
    report = detector.generate_anomaly_report(providers)
    print(report)
    
    # Save detailed results
    detailed_results = {}
    for provider in providers:
        if provider in detector.historical_data:
            detailed_results[provider] = detector.comprehensive_anomaly_detection(provider)
    
    with open('anomaly_detection_results.json', 'w') as f:
        json.dump(detailed_results, f, indent=2, default=str)
    
    print(f"\nDetailed results saved to anomaly_detection_results.json")

if __name__ == "__main__":
    main()
