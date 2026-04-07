# Common variables across GCP and Azure providers
# This file prevents "Duplicate variable declaration" errors when multiple cloud .tf files coexist.

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
