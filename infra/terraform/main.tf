# ---------------------------------------------------------------------------
# 1. Automated API Activation
# ---------------------------------------------------------------------------
locals {
  services = [
    "compute.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com", # Needed for WIF
    "sts.googleapis.com"             # Needed for WIF
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

  # Allow Google IAP and common SSH ranges
  source_ranges = ["35.235.240.0/20", "0.0.0.0/0"] 
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
# 3. Secret Manager Setup
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

    # Prevent concurrent apt issues
    while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 5; done
    
    # 1. Install Docker
    if ! command -v docker &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw
        curl -fsSL https://get.docker.com | sh
    fi
    
    # 2. Tailscale Setup
    curl -fsSL https://tailscale.com/install.sh | sh
    
    # Fetch key from Secret Manager
    TS_AUTH_KEY=$(gcloud secrets versions access latest --secret="TAILSCALE_AUTH_KEY")
    
    # FIXED: Use --advertise-tags for newer versions
    sudo tailscale up --authkey="$TS_AUTH_KEY" \
                      --hostname="mt5-engine-gcp" \
                      --advertise-tags=tag:trading \
                      --overwrite-admins
    
    # 3. Trust Tailscale Network
    sudo ufw allow in on tailscale0

    # 4. App Directory & Permissions
    mkdir -p /app
    if [ ! -d "/app/.git" ]; then
        git clone ${var.GITHUB_REPO_URL} /app
    fi
    chown -R danielmtz:danielmtz /app
    usermod -aG docker danielmtz
  EOT

  metadata = {
    ssh-keys = "danielmtz:${var.SSH_PUBLIC_KEY}"
  }

  service_account {
    # Full access to allow VM to fetch secrets
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

# ---------------------------------------------------------------------------
# 5. Workload Identity Federation (WIF)
# ---------------------------------------------------------------------------
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

  # Replace with your actual repository string
  attribute_condition = "assertion.repository == 'danielmtzbarba/quant-server-mt5'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# ---------------------------------------------------------------------------
# 6. IAM Permissions
# ---------------------------------------------------------------------------

# Allow the VM to read the Tailscale Secret
resource "google_project_iam_member" "vm_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_compute_instance.quant_vm.service_account[0].email}"
}

# ---------------------------------------------------------------------------
# 7. Outputs
# ---------------------------------------------------------------------------
output "vm_name" {
  value = google_compute_instance.quant_vm.name
}

output "vm_zone" {
  value = google_compute_instance.quant_vm.zone
}

output "wif_provider_name" {
  value = google_iam_workload_identity_pool_provider.github_provider.name
}