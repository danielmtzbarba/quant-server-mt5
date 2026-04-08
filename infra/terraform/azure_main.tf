terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.0" }
  }
}

provider "azurerm" {
  features {}
}

# Match existing name: quant-trading-rg
resource "azurerm_resource_group" "main" {
  name     = var.AZURE_RESOURCE_GROUP
  location = var.AZURE_LOCATION
}

# Match existing name: trading-network
resource "azurerm_virtual_network" "main" {
  name                = "trading-network"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# Match existing name: trading-subnet
resource "azurerm_subnet" "internal" {
  name                 = "trading-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]
}

# Match existing name: mt5-public-ip
resource "azurerm_public_ip" "main" {
  name                = "mt5-public-ip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard" # Matches your existing IP SKU
}

# Match existing name: mt5-nic
resource "azurerm_network_interface" "main" {
  name                = "mt5-nic"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.internal.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.main.id
  }
}

# Match existing name: mt5-engine-azure
resource "azurerm_linux_virtual_machine" "main" {
  name                = "mt5-engine-azure"
  resource_group_name  = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = var.AZURE_VM_SIZE
  admin_username      = "danielmtz"
  network_interface_ids = [azurerm_network_interface.main.id]

  admin_ssh_key {
    username   = "danielmtz"
    public_key = var.SSH_PUBLIC_KEY # Pass the new RSA key here
  }

  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Standard_LRS"
  }

  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts"
    version   = "latest"
  }

  # Base64 user_data as required by Azure
  user_data = base64encode(<<-EOT
    #!/bin/bash
    set -e
    # Install Docker
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    
    # Setup Tailscale (Host Mode)
    curl -fsSL https://tailscale.com/install.sh | sh
    tailscale up --authkey=${var.TAILSCALE_AUTH_KEY} --hostname=mt5-vm-azure --tag=tag:trading --overwrite-admins

    # Trust Tailscale
    ufw allow in on tailscale0
    ufw allow 22/tcp
    ufw allow 8000/tcp
    ufw allow 8086/tcp

    mkdir -p /app
    chown -R danielmtz:danielmtz /app
  EOT
  )
}