# Digital Ocean FinOps Terraform Configuration
terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

variable "environment" {
  description = "Environment type"
  type        = string
  default     = "dev"
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "region" {
  description = "Digital Ocean region"
  type        = string
  default     = "nyc1"
}

locals {
  # Cost-optimized droplet sizes based on environment
  droplet_sizes = {
    dev     = "s-1vcpu-1gb"
    staging = "s-2vcpu-2gb"
    prod    = "s-2vcpu-4gb"
  }
  
  # Tags for cost allocation
  common_tags = [
    "environment:${var.environment}",
    "cost-center:${var.environment}-compute",
    "owner:finops-team",
    "managed-by:terraform"
  ]
}

# Cost-optimized droplet
resource "digitalocean_droplet" "finops_app" {
  name     = "${var.environment}-finops-app"
  size     = local.droplet_sizes[var.environment]
  image    = "ubuntu-20-04-x64"
  region   = var.region
  tags     = local.common_tags
  
  # Cost optimization: Use monitoring for rightsizing decisions
  monitoring = true
  
  # Cost optimization: Enable backups for critical environments
  backups = var.environment == "prod"
  
  user_data = <<-EOF
              #!/bin/bash
              # Cost optimization: Install monitoring agent
              curl -sSL https://repos.insights.digitalocean.com/install.sh | sudo bash
              EOF
}

# Cost-optimized managed database
resource "digitalocean_database_cluster" "finops_db" {
  name       = "${var.environment}-finops-db"
  engine     = "pg"
  version    = "13"
  size       = var.environment == "prod" ? "db-s-1vcpu-2gb" : "db-s-1vcpu-1gb"
  region     = var.region
  node_count = var.environment == "prod" ? 2 : 1
  
  tags = concat(local.common_tags, ["service:database"])
}

# Cost-optimized spaces bucket
resource "digitalocean_spaces_bucket" "finops_data" {
  name   = "${var.environment}-finops-data"
  region = var.region
  
  # Cost optimization: Enable versioning for data protection
  versioning {
    enabled = var.environment == "prod"
  }
  
  # Cost optimization: Configure lifecycle rules
  lifecycle_rule {
    id      = "cost-optimization"
    enabled = true
    
    expiration {
      days = var.environment == "prod" ? 365 : 90
    }
    
    noncurrent_version_expiration {
      days = 30
    }
  }
}

# Load balancer for high availability (prod only)
resource "digitalocean_loadbalancer" "finops_lb" {
  count  = var.environment == "prod" ? 1 : 0
  name   = "${var.environment}-finops-lb"
  region = var.region
  
  forwarding_rule {
    entry_port     = 80
    entry_protocol = "http"
    
    target_port     = 80
    target_protocol = "http"
  }
  
  healthcheck {
    port     = 80
    protocol = "tcp"
  }
  
  droplet_tag = "environment:${var.environment}"
  
  tags = concat(local.common_tags, ["service:load-balancer"])
}

# Output cost-related information
output "monthly_estimated_cost" {
  description = "Estimated monthly cost for this environment"
  value = {
    droplet_cost = var.environment == "prod" ? 24 : 6  # $24/month for prod, $6/month for dev
    database_cost = var.environment == "prod" ? 30 : 15  # $30/month for prod, $15/month for dev
    storage_cost = 5  # $5/month for spaces
    load_balancer_cost = var.environment == "prod" ? 12 : 0  # $12/month for prod LB
    total = var.environment == "prod" ? 71 : 26
  }
}
