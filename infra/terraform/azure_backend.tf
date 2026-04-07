terraform {
  backend "azurerm" {
    resource_group_name  = "quant-trading-rg"
    storage_account_name = "mt5quantstatestorage26"
    container_name       = "tfstate"
    key                  = "azure.terraform.tfstate"
  }
}
