# Azure FinOps Cost Management Script
param(
    [string]$SubscriptionId,
    [string]$ResourceGroupName,
    [int]$DaysBack = 30
)

# Connect to Azure
Connect-AzAccount

# Set subscription context
Set-AzContext -SubscriptionId $SubscriptionId

class AzureFinOpsManager {
    [string]$SubscriptionId
    [string]$ResourceGroupName
    
    AzureFinOpsManager([string]$subId, [string]$rgName) {
        $this.SubscriptionId = $subId
        $this.ResourceGroupName = $rgName
    }
    
    [object] GetCostAnalysis([int]$days) {
        $endDate = Get-Date
        $startDate = $endDate.AddDays(-$days)
        
        $costs = Get-AzConsumptionUsageDetail -StartDate $startDate -EndDate $endDate |
            Where-Object { $_.InstanceName -like "*$($this.ResourceGroupName)*" }
        
        return $costs | Group-Object -Property InstanceName | ForEach-Object {
            [PSCustomObject]@{
                ResourceName = $_.Name
                TotalCost = ($_.Group | Measure-Object -Property PretaxCost -Sum).Sum
                UsageHours = ($_.Group | Measure-Object -Property UsageQuantity -Sum).Sum
                Service = $_.Group[0].ConsumedService
            }
        }
    }
    
    [object] GetOptimizationRecommendations() {
        $advisor = Get-AzAdvisorRecommendation | Where-Object { 
            $_.Category -eq "Cost" -and $_.Impact -eq "Medium" 
        }
        
        return $advisor | ForEach-Object {
            [PSCustomObject]@{
                ResourceId = $_.ResourceId
                Recommendation = $_.ShortDescription
                Impact = $_.Impact
                EstimatedSavings = $_.ExtendedProperties.EstimatedSavings
            }
        }
    }
    
    [void] GenerateCostReport([string]$outputPath) {
        $costs = $this.GetCostAnalysis(30)
        $recommendations = $this.GetOptimizationRecommendations()
        
        $report = [PSCustomObject]@{
            GeneratedAt = Get-Date
            SubscriptionId = $this.SubscriptionId
            ResourceGroup = $this.ResourceGroupName
            TotalCost = ($costs | Measure-Object -Property TotalCost -Sum).Sum
            ResourceCount = $costs.Count
            Recommendations = $recommendations
            CostBreakdown = $costs
        }
        
        $report | ConvertTo-Json -Depth 10 | Out-File -FilePath $outputPath
        Write-Host "Cost report generated: $outputPath"
    }
}

# Usage
$finops = [AzureFinOpsManager]::new($SubscriptionId, $ResourceGroupName)
$finops.GenerateCostReport("cost-report-$(Get-Date -Format 'yyyyMMdd').json")
