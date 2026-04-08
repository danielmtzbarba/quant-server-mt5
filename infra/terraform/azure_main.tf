terraform {
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
      # Allows Terraform to clean up the RG even if "ghost" resources exist
      prevent_deletion_if_contains_resources = false
    }
  }
}

# 1. Resource Group
resource "azurerm_resource_group" "main" {
  name     = var.AZURE_RESOURCE_GROUP
  location = var.AZURE_LOCATION
}

# 2. Networking Infrastructure
resource "azurerm_virtual_network" "main" {
  name                = "trading-network"
  address_space       = ["10.0.0.0/16"]
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_subnet" "internal" {
  name                 = "trading-subnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]
}

# 3. Public IP
resource "azurerm_public_ip" "main" {
  name                = "mt5-public-ip"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

# 4. Network Security Group (The Firewall)
resource "azurerm_network_security_group" "main" {
  name                = "trading-nsg"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  security_rule {
    name                       = "AllowSSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "AllowTailscaleUDP"
    priority                   = 1002
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Udp"
    source_port_range          = "*"
    destination_port_range     = "41641"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }
}

# 5. Network Interface (NIC)
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

# 6. Bind the Security Group to the NIC
resource "azurerm_network_interface_security_group_association" "main" {
  network_interface_id      = azurerm_network_interface.main.id
  network_security_group_id = azurerm_network_security_group.main.id
}

# 7. Linux Virtual Machine
resource "azurerm_linux_virtual_machine" "main" {
  name                = "mt5-engine-azure"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  size                = var.AZURE_VM_SIZE
  admin_username      = "danielmtz"
  network_interface_ids = [
    azurerm_network_interface.main.id,
  ]

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

  # Provisioning script (Cloud-Init)
  user_data = base64encode(<<-EOT
    #!/bin/bash
    set -e

    # 1. Wait for Network
    until ping -c 1 google.com; do sleep 5; done

    # 2. Install Docker
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker

    # 3. Install Tailscale
    curl -fsSL https://tailscale.com/install.sh | sh
    
    # 4. Login to Tailscale (Corrected Flag)
    tailscale up --authkey=${var.TAILSCALE_AUTH_KEY} \
                 --hostname=mt5-vm-azure \
                 --advertise-tags=tag:trading \
                 --overwrite-admins

    # 5. Configure Firewall (UFW)
    ufw allow in on tailscale0
    ufw allow 22/tcp
    ufw allow 8000/tcp
    ufw allow 8086/tcp
    ufw --force enable

    # 6. Set up project directories
    mkdir -p /app
    chown -R danielmtz:danielmtz /app
  EOT
  )

  tags = {
    environment = "trading"
  }
}