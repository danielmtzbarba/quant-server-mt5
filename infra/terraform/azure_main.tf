# Standard Azure Provider Config
terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.0" }
  }
}

provider "azurerm" {
  features {}
}

# Resource Group & Networking
resource "azurerm_resource_group" "rg" {
  name     = var.AZURE_RESOURCE_GROUP
  location = var.AZURE_LOCATION
}

resource "azurerm_virtual_network" "vnet" {
  name                = "mt5-vnet"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_subnet" "subnet" {
  name                 = "mt5-subnet"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_public_ip" "pip" {
  name                = "mt5-pip"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  allocation_method   = "Static"
}

resource "azurerm_network_interface" "nic" {
  name                = "mt5-nic"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.subnet.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.pip.id
  }
}

# Azure VM
resource "azurerm_linux_virtual_machine" "vm" {
  name                = "mt5-vm-azure"
  resource_group_name  = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  size                = var.AZURE_VM_SIZE
  admin_username      = "danielmtz"
  network_interface_ids = [azurerm_network_interface.nic.id]

  admin_ssh_key {
    username   = "danielmtz"
    public_key = var.SSH_PUBLIC_KEY
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

  user_data = base64encode(<<-EOT
    #!/bin/bash
    set -e
    # 1. Install Docker
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    usermod -aG docker danielmtz

    # 2. Install Tailscale
    curl -fsSL https://tailscale.com/install.sh | sh
    # Use host name 'mt5-vm-azure' to avoid collision with container
    tailscale up --authkey=${var.TAILSCALE_AUTH_KEY} --hostname=mt5-vm-azure --tag=tag:trading --overwrite-admins

    # 3. Security: Allow internal Tailscale traffic
    ufw allow in on tailscale0
    ufw allow 22/tcp
    ufw allow 8000/tcp
    ufw allow 8086/tcp

    # 4. App Directory
    mkdir -p /app
    chown -R danielmtz:danielmtz /app
    git clone ${var.GITHUB_REPO_URL} /app
  EOT
  )
}