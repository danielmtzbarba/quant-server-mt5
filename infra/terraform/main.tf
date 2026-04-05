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
    sudo apt-get install -y docker.io git docker-compose-plugin
    sudo systemctl start docker
    sudo systemctl enable docker

    # Clone the repository
    git clone ${var.github_repo_url} /app
    cd /app

    # Wait, the user wants us to ignore .env for a minute, 
    # but the app won't run without it in production unless 
    # we provide a fallback.
    # For now, we'll just prepare the directory.
    
    # Example command to run the stack once envs are manually placed or fetched:
    # docker compose -f infra/docker/server/docker-compose.yml up -d --build
  EOT

  # Ensure the service account has permission to read secrets if we automate fetching later
  service_account {
    scopes = ["cloud-platform"]
  }
}

output "instance_ip" {
  value = google_compute_instance.quant_vm.network_interface[0].access_config[0].nat_ip
}
