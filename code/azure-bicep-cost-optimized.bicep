@description('Environment type for cost optimization')
@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

@description('VM size optimized for environment')
param vmSize string = environment == 'prod' ? 'Standard_B2s' : 'Standard_B1s'

@description('Location for resources')
param location string = resourceGroup().location

// Cost-optimized VM with proper tagging
resource vm 'Microsoft.Compute/virtualMachines@2023-07-01' = {
  name: '${environment}-vm'
  location: location
  tags: {
    Environment: environment
    CostCenter: '${environment}-compute'
    Owner: 'finops-team'
    Schedule: environment == 'prod' ? 'always-on' : 'business-hours'
  }
  properties: {
    hardwareProfile: {
      vmSize: vmSize
    }
    osProfile: {
      computerName: '${environment}-vm'
      adminUsername: 'azureuser'
      adminPassword: 'P@ssw0rd123!'
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: 'UbuntuServer'
        sku: '18.04-LTS'
        version: 'latest'
      }
      osDisk: {
        name: '${environment}-osdisk'
        caching: 'ReadWrite'
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: environment == 'prod' ? 'Premium_LRS' : 'Standard_LRS'
        }
      }
    }
    networkProfile: {
      networkInterfaces: [
        {
          id: nic.id
        }
      ]
    }
  }
}

// Storage account with lifecycle management
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${environment}data${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  tags: {
    Environment: environment
    CostCenter: '${environment}-storage'
  }
  properties: {
    accessTier: 'Hot'
    lifecycleManagement: {
      rules: [
        {
          name: 'CostOptimization'
          enabled: true
          definition: {
            actions: {
              baseBlob: {
                tierToCool: {
                  daysAfterModificationGreaterThan: 30
                }
                tierToArchive: {
                  daysAfterModificationGreaterThan: 90
                }
              }
            }
            filters: {
              blobTypes: ['blockBlob']
            }
          }
        }
      ]
    }
  }
}
