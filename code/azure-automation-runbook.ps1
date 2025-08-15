# Azure Automation Runbook for FinOps Cost Optimization
# This runbook implements automated cost optimization workflows

param(
    [string]$ResourceGroupName,
    [string]$SubscriptionId,
    [int]$IdleThresholdHours = 24,
    [switch]$DryRun
)

# Connect to Azure using managed identity
Connect-AzAccount -Identity

# Set subscription context
Set-AzContext -SubscriptionId $SubscriptionId

class AzureFinOpsAutomation {
    [string]$ResourceGroupName
    [string]$SubscriptionId
    [int]$IdleThresholdHours
    [bool]$DryRun
    
    AzureFinOpsAutomation([string]$rgName, [string]$subId, [int]$threshold, [bool]$dryRun) {
        $this.ResourceGroupName = $rgName
        $this.SubscriptionId = $subId
        $this.IdleThresholdHours = $threshold
        $this.DryRun = $dryRun
    }
    
    [object] GetIdleVMs() {
        """Get VMs that have been idle for the specified threshold"""
        $vms = Get-AzVM -ResourceGroupName $this.ResourceGroupName
        $idleVMs = @()
        
        foreach ($vm in $vms) {
            # Get VM metrics for the last 24 hours
            $endTime = Get-Date
            $startTime = $endTime.AddHours(-$this.IdleThresholdHours)
            
            $metrics = Get-AzMetric -ResourceId $vm.Id -MetricName "Percentage CPU" -StartTime $startTime -EndTime $endTime -TimeGrain 01:00:00
            
            if ($metrics.Data) {
                $avgCpu = ($metrics.Data | Measure-Object -Property Total -Average).Average
                
                if ($avgCpu -lt 5) {  # Less than 5% CPU usage
                    $idleVMs += [PSCustomObject]@{
                        Name = $vm.Name
                        ResourceGroup = $vm.ResourceGroupName
                        Location = $vm.Location
                        Size = $vm.HardwareProfile.VmSize
                        AverageCPU = $avgCpu
                        EstimatedMonthlyCost = $this.EstimateVMCost($vm.HardwareProfile.VmSize)
                    }
                }
            }
        }
        
        return $idleVMs
    }
    
    [object] GetUnusedResources() {
        """Get unused resources for cleanup"""
        $unusedResources = @()
        
        # Check for unattached disks
        $disks = Get-AzDisk -ResourceGroupName $this.ResourceGroupName | Where-Object { $_.DiskState -eq "Unattached" }
        foreach ($disk in $disks) {
            $unusedResources += [PSCustomObject]@{
                Type = "Disk"
                Name = $disk.Name
                ResourceGroup = $disk.ResourceGroupName
                EstimatedMonthlyCost = $this.EstimateDiskCost($disk.DiskSizeGB, $disk.Sku.Name)
                Action = "Delete"
            }
        }
        
        # Check for unused public IPs
        $publicIPs = Get-AzPublicIpAddress -ResourceGroupName $this.ResourceGroupName | Where-Object { $_.IpConfiguration -eq $null }
        foreach ($ip in $publicIPs) {
            $unusedResources += [PSCustomObject]@{
                Type = "Public IP"
                Name = $ip.Name
                ResourceGroup = $ip.ResourceGroupName
                EstimatedMonthlyCost = 3.65  # Standard public IP cost
                Action = "Delete"
            }
        }
        
        return $unusedResources
    }
    
    [void] OptimizeVMSizes() {
        """Optimize VM sizes based on usage patterns"""
        $vms = Get-AzVM -ResourceGroupName $this.ResourceGroupName
        
        foreach ($vm in $vms) {
            # Get VM usage metrics
            $endTime = Get-Date
            $startTime = $endTime.AddDays(-7)
            
            $cpuMetrics = Get-AzMetric -ResourceId $vm.Id -MetricName "Percentage CPU" -StartTime $startTime -EndTime $endTime -TimeGrain 01:00:00
            $memoryMetrics = Get-AzMetric -ResourceId $vm.Id -MetricName "Available Memory Bytes" -StartTime $startTime -EndTime $endTime -TimeGrain 01:00:00
            
            if ($cpuMetrics.Data -and $memoryMetrics.Data) {
                $avgCpu = ($cpuMetrics.Data | Measure-Object -Property Total -Average).Average
                $avgMemory = ($memoryMetrics.Data | Measure-Object -Property Total -Average).Average
                
                # Determine if VM is oversized
                $recommendedSize = $this.GetRecommendedVMSize($vm.HardwareProfile.VmSize, $avgCpu, $avgMemory)
                
                if ($recommendedSize -ne $vm.HardwareProfile.VmSize) {
                    $currentCost = $this.EstimateVMCost($vm.HardwareProfile.VmSize)
                    $recommendedCost = $this.EstimateVMCost($recommendedSize)
                    $savings = $currentCost - $recommendedCost
                    
                    Write-Output "VM $($vm.Name) can be resized from $($vm.HardwareProfile.VmSize) to $recommendedSize (Monthly savings: `$$savings)"
                    
                    if (-not $this.DryRun) {
                        # Stop VM before resizing
                        Stop-AzVM -ResourceGroupName $vm.ResourceGroupName -Name $vm.Name -Force
                        
                        # Resize VM
                        $vm.HardwareProfile.VmSize = $recommendedSize
                        Update-AzVM -ResourceGroupName $vm.ResourceGroupName -VM $vm
                        
                        # Start VM
                        Start-AzVM -ResourceGroupName $vm.ResourceGroupName -Name $vm.Name
                    }
                }
            }
        }
    }
    
    [void] ScheduleVMs() {
        """Schedule VMs based on business hours"""
        $vms = Get-AzVM -ResourceGroupName $this.ResourceGroupName
        
        foreach ($vm in $vms) {
            # Check if VM has schedule tag
            $scheduleTag = $vm.Tags["Schedule"]
            
            if ($scheduleTag -eq "business-hours") {
                $currentHour = (Get-Date).Hour
                $isWeekend = (Get-Date).DayOfWeek -in @("Saturday", "Sunday")
                
                # Business hours: 9 AM - 6 PM, Monday-Friday
                $shouldBeRunning = -not $isWeekend -and $currentHour -ge 9 -and $currentHour -lt 18
                $isRunning = $vm.PowerState -eq "VM running"
                
                if ($shouldBeRunning -and -not $isRunning) {
                    Write-Output "Starting VM $($vm.Name) for business hours"
                    if (-not $this.DryRun) {
                        Start-AzVM -ResourceGroupName $vm.ResourceGroupName -Name $vm.Name
                    }
                }
                elseif (-not $shouldBeRunning -and $isRunning) {
                    Write-Output "Stopping VM $($vm.Name) outside business hours"
                    if (-not $this.DryRun) {
                        Stop-AzVM -ResourceGroupName $vm.ResourceGroupName -Name $vm.Name -Force
                    }
                }
            }
        }
    }
    
    [double] EstimateVMCost([string]$vmSize) {
        """Estimate monthly cost for VM size"""
        $costMap = @{
            "Standard_B1s" = 7.30
            "Standard_B2s" = 14.60
            "Standard_D2s_v3" = 70.08
            "Standard_D4s_v3" = 140.16
            "Standard_E2s_v3" = 70.08
            "Standard_E4s_v3" = 140.16
        }
        
        return $costMap[$vmSize] ?? 100.0  # Default estimate
    }
    
    [double] EstimateDiskCost([int]$sizeGB, [string]$sku) {
        """Estimate monthly cost for disk"""
        $costPerGB = if ($sku -eq "Premium_LRS") { 0.12 } else { 0.05 }
        return $sizeGB * $costPerGB
    }
    
    [string] GetRecommendedVMSize([string]$currentSize, [double]$avgCpu, [double]$avgMemory) {
        """Get recommended VM size based on usage"""
        # Simple logic for demonstration
        if ($avgCpu -lt 10 -and $currentSize -like "*D4s*") {
            return "Standard_D2s_v3"
        }
        elseif ($avgCpu -lt 20 -and $currentSize -like "*D2s*") {
            return "Standard_B2s"
        }
        
        return $currentSize
    }
    
    [void] GenerateReport() {
        """Generate optimization report"""
        $idleVMs = $this.GetIdleVMs()
        $unusedResources = $this.GetUnusedResources()
        
        $report = [PSCustomObject]@{
            GeneratedAt = Get-Date
            SubscriptionId = $this.SubscriptionId
            ResourceGroup = $this.ResourceGroupName
            IdleVMs = $idleVMs
            UnusedResources = $unusedResources
            TotalPotentialSavings = ($idleVMs | Measure-Object -Property EstimatedMonthlyCost -Sum).Sum + ($unusedResources | Measure-Object -Property EstimatedMonthlyCost -Sum).Sum
        }
        
        # Convert to JSON and save to storage account
        $reportJson = $report | ConvertTo-Json -Depth 10
        Write-Output $reportJson
        
        # Send to Log Analytics if configured
        if (Get-Command "Send-AzLogAnalyticsData" -ErrorAction SilentlyContinue) {
            Send-AzLogAnalyticsData -WorkspaceId "your-workspace-id" -LogType "FinOpsOptimization" -Data $reportJson
        }
    }
}

# Main execution
try {
    $automation = [AzureFinOpsAutomation]::new($ResourceGroupName, $SubscriptionId, $IdleThresholdHours, $DryRun)
    
    Write-Output "Starting Azure FinOps automation for resource group: $ResourceGroupName"
    
    # Run optimization tasks
    $automation.ScheduleVMs()
    $automation.OptimizeVMSizes()
    $automation.GenerateReport()
    
    Write-Output "Azure FinOps automation completed successfully"
}
catch {
    Write-Error "Error in Azure FinOps automation: $($_.Exception.Message)"
    throw
}
