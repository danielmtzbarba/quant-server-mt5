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
  default     = "East US"
}

variable "AZURE_INSTANCE_NAME" {
  description = "The name of the Azure VM."
  type        = string
  default     = "mt5-engine-azure"
}

variable "AZURE_VM_SIZE" {
  description = "The size of the Azure VM (using B2s as a temporary workaround for B1s capacity constraints in eastus)."
  type        = string
  default     = "Standard_B2s"
}

