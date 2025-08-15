# GCP FinOps Terraform Configuration
terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

variable "project_id" {
  description = "GCP Project ID"
  type        = string
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
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

locals {
  # Cost-optimized machine types based on environment
  machine_types = {
    dev     = "e2-micro"
    staging = "e2-small"
    prod    = "e2-medium"
  }
  
  # Cost-optimized disk types
  disk_types = {
    dev     = "pd-standard"
    staging = "pd-standard"
    prod    = "pd-ssd"
  }
}

# Cost-optimized compute instance
resource "google_compute_instance" "finops_vm" {
  name         = "${var.environment}-finops-vm"
  machine_type = local.machine_types[var.environment]
  zone         = "${var.region}-a"

  tags = [
    "environment-${var.environment}",
    "cost-center-${var.environment}-compute",
    "owner-finops-team"
  ]

  boot_disk {
    initialize_params {
      image  = "debian-cloud/debian-11"
      type   = local.disk_types[var.environment]
      size   = var.environment == "prod" ? 50 : 20
    }
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  metadata = {
    environment = var.environment
    cost-center = "${var.environment}-compute"
    owner       = "finops-team"
    schedule    = var.environment == "prod" ? "always-on" : "business-hours"
  }

  # Cost optimization: Use preemptible instances for non-prod
  scheduling {
    preemptible = var.environment != "prod"
  }
}

# Cost-optimized storage bucket with lifecycle
resource "google_storage_bucket" "finops_data" {
  name          = "${var.project_id}-${var.environment}-data"
  location      = var.region
  force_destroy = var.environment != "prod"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = {
    environment = var.environment
    cost-center = "${var.environment}-storage"
    owner       = "finops-team"
  }
}

# Budget alert for cost control
resource "google_billing_budget" "finops_budget" {
  billing_account = data.google_billing_account.account.id
  display_name    = "${var.environment} FinOps Budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units         = var.environment == "prod" ? "1000" : "100"
    }
  }

  threshold_rules {
    threshold_percent = 0.5
  }
  
  threshold_rules {
    threshold_percent = 0.8
  }
  
  threshold_rules {
    threshold_percent = 1.0
  }
}

data "google_billing_account" "account" {
  display_name = "My Billing Account"
  open         = true
}
