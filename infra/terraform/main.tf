terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    http = {
      source  = "hashicorp/http"
      version = "~> 3.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  zone    = var.zone
}

# 1. Automated API Activation (Self-Healing)
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

# 2. Fetch current public IP for whitelisting
data "http" "my_ip" {
  url = "http://checkip.amazonaws.com"
}

# 2. Firewall: Allow SSH via IAP (Zero-Exposure)
resource "google_compute_firewall" "allow_ssh" {
  name    = "allow-ssh-iap"
  network = "default"

  depends_on = [google_project_service.apis]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # Only allow Google's IAP Proxy range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["quant-server"]
}

# 3. Firewall: Allow HTTP/HTTPS for Webhooks (Caddy)
resource "google_compute_firewall" "allow_web" {
  name    = "allow-web-traffic"
  network = "default"

  depends_on = [google_project_service.apis]

  allow {
    protocol = "tcp"
    ports    = ["80", "443"]
  }

  # Open to public for Let's Encrypt verification + Meta Webhooks
  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["quant-server"]
}

# 4. Reserve Static External IP (Zero-Touch Identity)
resource "google_compute_address" "static_ip" {
  name       = "quant-server-static-ip"
  project    = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

# 5. Firewall: Restricted ports (8001-8002)
resource "google_compute_firewall" "restricted_access" {
  name    = "allow-restricted-access"
  network = "default"

  depends_on = [google_project_service.apis]

  allow {
    protocol = "tcp"
    ports    = ["8001", "8002"]
  }

  # Restrict to: My IP
  source_ranges = [
    "${chomp(data.http.my_ip.response_body)}/32"
  ]
  target_tags = ["quant-server"]
}

# 6. Secret Manager: Store sensitive tokens
resource "google_secret_manager_secret" "openai_key" {
  secret_id  = "OPENAI_API_KEY"
  depends_on = [google_project_service.apis]
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "whatsapp_api_token" {
  secret_id  = "WHATSAPP_API_TOKEN"
  depends_on = [google_project_service.apis]
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "whatsapp_auth_token" {
  secret_id  = "WHATSAPP_AUTH_TOKEN"
  depends_on = [google_project_service.apis]
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "admin_token" {
  secret_id  = "ADMIN_TOKEN"
  depends_on = [google_project_service.apis]
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "tailscale_auth_key" {
  secret_id  = "TAILSCALE_AUTH_KEY"
  depends_on = [google_project_service.apis]
  replication {
    auto {}
  }
}

# 5. GCE Instance (e2-micro)
resource "google_compute_instance" "quant_vm" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.zone
  tags         = ["quant-server"]

  depends_on = [google_project_service.apis]

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

  # Startup script to pull the app and run it
  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -e

    # 1. Wait for apt lock (Debian/Ubuntu boot updates)
    echo "Waiting for apt lock..."
    while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do
       sleep 5
    done
    
    # 2. Check if tools are already installed (Idempotency)
    if ! command -v git &> /dev/null || ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        echo "Installing Prerequisites..."
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg lsb-release git

        # 3. Add Docker GPG Key and Repo
        sudo mkdir -p /etc/apt/keyrings
        if [ ! -f /etc/apt/keyrings/docker.gpg ]; then
            curl -fsSL https://download.docker.com/linux/debian/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
        fi
        
        echo \
          "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
          $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

        # 4. Install Docker Engine and Plugins
        sudo apt-get update
        sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    else
        echo "Docker and Git already installed. Skipping..."
    fi
    
    # 5. Enable 2GB Swap (Crucial for e2-micro)
    if [ ! -f /swapfile ]; then
        sudo fallocate -l 2G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    else
        echo "Swapfile exists. Skipping..."
    fi
    
    # 6. Start Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    # 7. Install Tailscale (Networking)
    if ! command -v tailscale &> /dev/null; then
        curl -fsSL https://tailscale.com/install.sh | sh
    else
        echo "Tailscale already installed. Skipping..."
    fi
    
    # 8. Authenticate Tailscale Automatically
    echo "Wait for gcloud to be ready"
    TS_AUTH_KEY=$(gcloud secrets versions access latest --secret="TAILSCALE_AUTH_KEY" || echo "")
    if [ -n "$TS_AUTH_KEY" ]; then
        if sudo tailscale status | grep -q "Logged out"; then
             sudo tailscale up --authkey="$TS_AUTH_KEY" --hostname="mt5-quant-server-vm" --accept-routes
        else
             echo "Tailscale already active. Skipping login..."
        fi
    else
        echo "Tailscale Auth Key not found or inaccessible. Manual login required."
    fi
    
    # 9. Clone Repository (for infra config)
    if [ ! -d /app ]; then
        mkdir -p /app
        git clone ${var.github_repo_url} /app
    else
        echo "Directory /app exists. Pulling latest..."
        cd /app && git pull
    fi
    
    # 10. Pull pre-built images from GHCR
    cd /app
    export GITHUB_REPOSITORY_OWNER=danielmtzbarba
    docker compose -f infra/docker/server/docker-compose.yml pull
    
    # 11. Hand over ownership to the deployer user
    chown -R danielmtz:danielmtz /app
    usermod -aG docker danielmtz
    
    # 12. Success marker
    echo "GCP VM Ready. Setup Tailscale and copy your .env files to /app/infra/envs/"
  EOT

  # Inject SSH public key for GitHub Actions deployment
  metadata = {
    ssh-keys = "danielmtz:${var.ssh_public_key}"
  }

  # Ensure the service account has permission to read secrets
  service_account {
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# 5. Workload Identity Federation (Zero-Secret Auth for GitHub)
resource "google_iam_workload_identity_pool" "github_pool" {
  workload_identity_pool_id = "github-pool"
  display_name              = "GitHub Pool"
  description               = "Identity pool for GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github_provider" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Provider"

  attribute_mapping = {
    "google.subject"             = "assertion.sub"
    "attribute.actor"            = "assertion.actor"
    "attribute.repository"       = "assertion.repository"
    "attribute.repository_owner" = "assertion.repository_owner"
  }

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_condition = "assertion.repository == 'danielmtzbarba/quant-server-mt5'"
}

# Allow GitHub to impersonate the Service Account
# Restrict to the specific repository: danielmtzbarba/quant-server-mt5
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/github-actions-deployer@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/danielmtzbarba/quant-server-mt5"
}

# Allow the VM to read secrets (required for Tailscale Auto-Join)
resource "google_project_iam_member" "vm_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:861553998922-compute@developer.gserviceaccount.com"
}

# Allow GitHub to use IAP Tunnels
resource "google_project_iam_member" "gha_iap_accessor" {
  project = var.project_id
  role    = "roles/iap.tunnelResourceAccessor"
  member  = "serviceAccount:github-actions-deployer@${var.project_id}.iam.gserviceaccount.com"
}

# Allow GitHub to manage instances (needed for gcloud compute ssh)
resource "google_project_iam_member" "gha_instance_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:github-actions-deployer@${var.project_id}.iam.gserviceaccount.com"
}

output "wif_provider_name" {
  value = google_iam_workload_identity_pool_provider.github_provider.name
}

output "vm_name" {
  value = google_compute_instance.quant_vm.name
}

output "vm_zone" {
  value = google_compute_instance.quant_vm.zone
}

output "vm_ip" {
  value       = google_compute_instance.quant_vm.network_interface[0].access_config[0].nat_ip
  description = "External IP of the GCE VM."
}
