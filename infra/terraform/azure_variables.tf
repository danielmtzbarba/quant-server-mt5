variable "azure_subscription_id" {
  description = "The Azure subscription ID."
  type        = string
}

variable "azure_client_id" {
  description = "The Azure client ID (Service Principal)."
  type        = string
}

variable "azure_client_secret" {
  description = "The Azure client secret (Service Principal)."
  type        = string
  sensitive   = true
}

variable "azure_tenant_id" {
  description = "The Azure tenant ID."
  type        = string
}

variable "azure_resource_group" {
  description = "The name of the Azure resource group."
  type        = string
  default     = "quant-trading-rg"
}

variable "azure_location" {
  description = "The Azure region for the deployment."
  type        = string
  default     = "East US"
}

variable "azure_instance_name" {
  description = "The name of the Azure VM."
  type        = string
  default     = "mt5-engine-azure"
}

variable "azure_vm_size" {
  description = "The size of the Azure VM."
  type        = string
  default     = "Standard_B1s"
}
