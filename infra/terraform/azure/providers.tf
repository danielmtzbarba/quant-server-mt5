terraform {
  required_version = ">= 1.5.0"

  backend "azurerm" {
    resource_group_name  = "quant-trading-rg"
    storage_account_name = "mt5quantstatestorage26"
    container_name       = "tfstate"
    key                  = "azure.terraform.tfstate"
  }

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {
    resource_group {
      # Good for dev/trading bot: allows 'terraform destroy' to actually work
      prevent_deletion_if_contains_resources = false
    }
    virtual_machine {
      # Ensures the OS disk is deleted when the VM is deleted
      delete_os_disk_on_deployment_deletion = true
    }
  }
}