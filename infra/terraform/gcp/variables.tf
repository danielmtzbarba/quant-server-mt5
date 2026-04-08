variable "PROJECT_ID" {
  description = "The GCP project ID to deploy to."
  type        = string
}

variable "REGION" {
  description = "The GCP region for the deployment."
  type        = string
  default     = "us-central1"
}

variable "ZONE" {
  description = "The GCP zone for the deployment."
  type        = string
  default     = "us-west3-a"
}

variable "INSTANCE_NAME" {
  description = "The name of the GCE instance."
  type        = string
  default     = "mt5-engine-gcp"
}

variable "MACHINE_TYPE" {
  description = "The machine type for the instance."
  type        = string
  default     = "e2-micro"
}

variable "GITHUB_REPO_URL" {
  description = "The URL of the GitHub repository to clone."
  type        = string
}

variable "SSH_PUBLIC_KEY" {
  description = "SSH public key to inject into the VM for GitHub Actions deployment."
  type        = string
}

variable "ADMIN_IP" {
  description = "Whitelisted IP address for restricted ports and SSH access."
  type        = string
}

variable "TAILSCALE_AUTH_KEY" {
  type        = string
  description = "Tailscale ephemeral auth key from GitHub Secrets"
  sensitive   = true
}

