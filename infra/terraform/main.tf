# GCP Provider Config
terraform {
  required_providers {
    google = { source = "hashicorp/google", version = "~> 5.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# API Activation
resource "google_project_service" "apis" {
  for_each = toset(["compute.googleapis.com", "secretmanager.googleapis.com", "iam.googleapis.com"])
  project  = var.project_id
  service  = each.key
  disable_on_destroy = false
}

# Secrets with FIXED Multi-line replication
resource "google_secret_manager_secret" "tailscale_auth_key" {
  secret_id = "TAILSCALE_AUTH_KEY"
  replication {
    auto {} # Fixed: Must be on its own line
  }
}

# (Repeat same multi-line replication for your other secrets: openai_key, etc.)

# GCP Instance
resource "google_compute_instance" "quant_vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["quant-server"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 30
    }
  }

  network_interface {
    network = "default"
    access_config {} # Dynamic IP
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    # 1. Install Tools
    apt-get update && apt-get install -y git curl ufw
    curl -fsSL https://get.docker.com | sh
    
    # 2. Tailscale with TAGGING
    curl -fsSL https://tailscale.com/install.sh | sh
    TS_KEY=$(gcloud secrets versions access latest --secret="TAILSCALE_AUTH_KEY")
    tailscale up --authkey="$TS_KEY" --hostname=mt5-engine-gcp --tag=tag:trading --overwrite-admins
    
    # 3. Local Firewall Trust
    ufw allow in on tailscale0
    
    # 4. App Setup
    mkdir -p /app
    git clone ${var.GITHUB_REPO_URL} /app
    chown -R danielmtz:danielmtz /app
    usermod -aG docker danielmtz
  EOT

  metadata = {
    ssh-keys = "danielmtz:${var.SSH_PUBLIC_KEY}"
  }

  service_account {
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# Grant the VM access to read its own secrets
resource "google_project_iam_member" "vm_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_compute_instance.quant_vm.service_account[0].email}"
}