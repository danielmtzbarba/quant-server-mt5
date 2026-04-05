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

# 1. Fetch current public IP for whitelisting
data "http" "my_ip" {
  url = "http://checkip.amazonaws.com"
}

# 2. Firewall: Allow SSH and internal microservice ports (8001-8003)
resource "google_compute_firewall" "restricted_access" {
  name    = "allow-restricted-access"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["22", "8001", "8002", "8003"]
  }

  # Restrict to: My IP + Meta Webhook Ranges
  source_ranges = [
    "${chomp(data.http.my_ip.response_body)}/32",
    "31.13.24.0/21", "45.64.40.0/22", "66.220.144.0/20", 
    "69.63.176.0/20", "69.171.224.0/19", "74.123.0.0/16", 
    "103.4.96.0/22", "129.134.0.0/17", "157.240.0.0/16", 
    "173.252.64.0/18", "179.60.192.0/22", "185.60.216.0/22", 
    "204.15.20.0/22"
  ]
  target_tags = ["quant-server"]
}

# 3. Secret Manager: Store sensitive tokens
resource "google_secret_manager_secret" "openai_key" {
  secret_id = "OPENAI_API_KEY"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "whatsapp_api_token" {
  secret_id = "WHATSAPP_API_TOKEN"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "whatsapp_auth_token" {
  secret_id = "WHATSAPP_AUTH_TOKEN"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "admin_token" {
  secret_id = "ADMIN_TOKEN"
  replication {
    auto {}
  }
}

  # 4. GCE Instance (e2-micro)
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
      # Static External IP or Ephemeral
    }
  }

  # Startup script to pull the app and run it
  metadata_startup_script = <<-EOT
    #!/bin/bash
    sudo apt-get update
    sudo apt-get install -y docker.io git docker-compose-plugin curl

    # 1. Enable 2GB Swap (Crucial for e2-micro)
    if [ ! -f /swapfile ]; then
        sudo fallocate -l 2G /swapfile
        sudo chmod 600 /swapfile
        sudo mkswap /swapfile
        sudo swapon /swapfile
        echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    fi

    # 2. Start Docker
    sudo systemctl start docker
    sudo systemctl enable docker

    # 2. Install Tailscale (Networking)
    curl -fsSL https://tailscale.com/install.sh | sh
    # Note: User must still run 'sudo tailscale up' manually to authenticate

    # 3. Clone Repository (for infra config)
    mkdir -p /app
    git clone ${var.github_repo_url} /app
    cd /app

    # 4. Pull pre-built images from GHCR
    # Ensuring the lowest startup time for the e2-micro
    export GITHUB_REPOSITORY_OWNER=danielmtzbarba
    docker compose -f infra/docker/server/docker-compose.yml pull

    # 5. Success marker
    echo "GCP VM Ready. Setup Tailscale and copy your .env files to /app/infra/envs/"
  EOT

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
}

# Allow GitHub to impersonate the Service Account
# Restrict to the specific repository: danielmtzbarba/quant-server-mt5
resource "google_service_account_iam_member" "wif_binding" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/github-actions-deployer@${var.project_id}.iam.gserviceaccount.com"
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/danielmtzbarba/quant-server-mt5"
}

output "wif_provider_name" {
  value = google_iam_workload_identity_pool_provider.github_provider.name
}
