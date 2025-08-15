# Multi-Cloud FinOps Terraform Configuration
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

variable "environment" {
  description = "Environment type"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "azure_location" {
  description = "Azure Location"
  type        = string
  default     = "East US"
}

variable "gcp_region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

locals {
  common_tags = {
    Environment = var.environment
    CostCenter  = "${var.environment}-multi-cloud"
    Owner       = "finops-team"
    ManagedBy   = "terraform"
  }
}

# AWS Resources
provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "aws_vm" {
  count = var.environment == "prod" ? 2 : 1
  
  ami           = "ami-12345678"
  instance_type = var.environment == "prod" ? "t3.medium" : "t3.micro"
  
  tags = merge(local.common_tags, {
    Cloud = "aws"
    Name  = "${var.environment}-aws-vm-${count.index + 1}"
  })
}

# Azure Resources
provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.environment}-finops-rg"
  location = var.azure_location
  
  tags = local.common_tags
}

resource "azurerm_virtual_machine" "azure_vm" {
  count = var.environment == "prod" ? 2 : 1
  
  name                  = "${var.environment}-azure-vm-${count.index + 1}"
  location              = azurerm_resource_group.rg.location
  resource_group_name   = azurerm_resource_group.rg.name
  network_interface_ids = [azurerm_network_interface.nic[count.index].id]
  vm_size               = var.environment == "prod" ? "Standard_B2s" : "Standard_B1s"
  
  storage_image_reference {
    publisher = "Canonical"
    offer     = "UbuntuServer"
    sku       = "18.04-LTS"
    version   = "latest"
  }
  
  storage_os_disk {
    name              = "${var.environment}-azure-osdisk-${count.index + 1}"
    caching           = "ReadWrite"
    create_option     = "FromImage"
    managed_disk_type = "Standard_LRS"
  }
  
  os_profile {
    computer_name  = "${var.environment}-azure-vm-${count.index + 1}"
    admin_username = "azureuser"
    admin_password = "P@ssw0rd123!"
  }
  
  tags = merge(local.common_tags, {
    Cloud = "azure"
  })
}

# GCP Resources
provider "google" {
  project = "your-gcp-project"
  region  = var.gcp_region
}

resource "google_compute_instance" "gcp_vm" {
  count = var.environment == "prod" ? 2 : 1
  
  name         = "${var.environment}-gcp-vm-${count.index + 1}"
  machine_type = var.environment == "prod" ? "e2-medium" : "e2-micro"
  zone         = "${var.gcp_region}-a"
  
  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = var.environment == "prod" ? 50 : 20
    }
  }
  
  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }
  
  labels = merge(local.common_tags, {
    cloud = "gcp"
  })
}

# Cost monitoring outputs
output "monthly_cost_estimate" {
  description = "Estimated monthly cost by cloud provider"
  value = {
    aws = {
      instances = var.environment == "prod" ? 2 * 30 : 1 * 8  # $30/month for prod, $8/month for dev
      total     = var.environment == "prod" ? 60 : 8
    }
    azure = {
      instances = var.environment == "prod" ? 2 * 25 : 1 * 7  # $25/month for prod, $7/month for dev
      total     = var.environment == "prod" ? 50 : 7
    }
    gcp = {
      instances = var.environment == "prod" ? 2 * 20 : 1 * 6  # $20/month for prod, $6/month for dev
      total     = var.environment == "prod" ? 40 : 6
    }
    total = var.environment == "prod" ? 150 : 21
  }
}
