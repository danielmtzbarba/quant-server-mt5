variable "AZURE_SUBSCRIPTION_ID" {
  description = "The Azure subscription ID."
  type        = string
}

variable "AZURE_CLIENT_ID" {
  description = "The Azure client ID (Service Principal)."
  type        = string
}

variable "AZURE_CLIENT_SECRET" {
  description = "The Azure client secret (Service Principal)."
  type        = string
  sensitive   = true
}

variable "AZURE_TENANT_ID" {
  description = "The Azure tenant ID."
  type        = string
}

variable "AZURE_RESOURCE_GROUP" {
  description = "The name of the Azure resource group."
  type        = string
  default     = "quant-trading-rg"
}

variable "AZURE_LOCATION" {
  description = "The Azure region for the deployment."
  type        = string
  default     = "westeurope"
}

variable "AZURE_INSTANCE_NAME" {
  description = "The name of the Azure VM."
  type        = string
  default     = "mt5-engine-azure"
}

variable "AZURE_VM_SIZE" {
  description = "The size of the Azure VM."
  type        = string
  default     = "Standard_B2ts_v2"
}

variable "TAILSCALE_AUTH_KEY" {
  description = "The Tailscale Auth Key to automatically join the tailnet on boot."
  type        = string
  sensitive   = true
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


