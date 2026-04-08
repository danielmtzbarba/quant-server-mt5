terraform {
  # ONE backend to rule them all (GCS is fine for both Azure and GCP states)
  backend "gcs" {
    bucket = "terraform-state-project-221a7ff0-ceb3-422b-bf0"
    prefix = "terraform/state"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

# Keep your provider configurations here
provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}