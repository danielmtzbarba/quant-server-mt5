terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# ---------------------------------------------------------------------------
# 1. Automated API Activation
# ---------------------------------------------------------------------------
locals {
  services = [
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com"
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.services)
  project  = var.project_id
  service  = each.key

  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# 2. Networking & Firewalls
# ---------------------------------------------------------------------------
resource "google_compute_address" "static_ip" {
  name       = "quant-server-static-ip"
  project    = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh-iap"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["quant-server"]
}

resource "google_compute_firewall" "allow_web" {
  name    = "allow-web-traffic"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["quant-server"]
}

resource "google_compute_firewall" "allow_admin_vault" {
  name    = "allow-admin-vault"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8001", "8002"]
  }

  source_ranges = ["${var.ADMIN_IP}/32"]
  target_tags   = ["quant-server"]
}

# ---------------------------------------------------------------------------
# 3. Secret Manager (Corrected Syntax)
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret" "tailscale_auth_key" {
  secret_id = "TAILSCALE_AUTH_KEY"
  replication {
    auto {}
  }
}

# ---------------------------------------------------------------------------
# 4. GCE Instance
# ---------------------------------------------------------------------------
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
    access_config {
      nat_ip = google_compute_address.static_ip.address
    }
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -e
    while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done
    
    if ! command -v docker &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw
        curl -fsSL https://get.docker.com | sh
    fi
    
    # Tailscale Setup
    curl -fsSL https://tailscale.com/install.sh | sh
    TS_AUTH_KEY=$(gcloud secrets versions access latest --secret="TAILSCALE_AUTH_KEY")
    sudo tailscale up --authkey="$TS_AUTH_KEY" --hostname="mt5-engine-gcp" --tag=tag:trading --overwrite-admins
    
    # Trust Tailscale
    sudo ufw allow in on tailscale0

    # App Directory
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

# ---------------------------------------------------------------------------
# 5. IAM & Workload Identity
# ---------------------------------------------------------------------------
resource "google_project_iam_member" "vm_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_compute_instance.quant_vm.service_account[0].email}"
}

output "vm_name" {
  value = google_compute_instance.quant_vm.name
}

output "vm_zone" {
  value = google_compute_instance.quant_vm.zone
}