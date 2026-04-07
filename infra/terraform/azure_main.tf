provider "azurerm" {
  features {}
  subscription_id = var.azure_subscription_id
  client_id       = var.azure_client_id
  client_secret   = var.azure_client_secret
  tenant_id       = var.azure_tenant_id
}

# 1. Virtual Network
resource "azurerm_virtual_network" "main" {
  name                = "trading-network"
  address_space       = ["10.0.0.0/16"]
  location            = var.azure_location
  resource_group_name = var.azure_resource_group
}

# 2. Subnet
resource "azurerm_subnet" "internal" {
  name                 = "trading-subnet"
  resource_group_name  = var.azure_resource_group
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]
}

# 3. Public IP (Required for SSH/Deployment from Github)
resource "azurerm_public_ip" "main" {
  name                = "mt5-public-ip"
  resource_group_name = var.azure_resource_group
  location            = var.azure_location
  allocation_method   = "Dynamic"
}

# 4. Network Security Group (Whitelist Admin SSH only)
resource "azurerm_network_security_group" "main" {
  name                = "trading-nsg"
  location            = var.azure_location
  resource_group_name = var.azure_resource_group

  security_rule {
    name                       = "SSH"
    priority                   = 1001
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = "${var.admin_ip}/32"
    destination_address_prefix = "*"
  }
}

# 5. Network Interface
resource "azurerm_network_interface" "main" {
  name                = "mt5-nic"
  location            = var.azure_location
  resource_group_name = var.azure_resource_group

  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.internal.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.main.id
  }
}

resource "azurerm_network_interface_security_group_association" "main" {
  network_interface_id      = azurerm_network_interface.main.id
  network_security_group_id = azurerm_network_security_group.main.id
}

# 6. Linux Virtual Machine (Standard_B1s)
resource "azurerm_linux_virtual_machine" "main" {
  name                = var.azure_instance_name
  resource_group_name = var.azure_resource_group
  location            = var.azure_location
  size                = var.azure_vm_size
  admin_username      = "danielmtz"

  network_interface_ids = [
    azurerm_network_interface.main.id,
  ]

  admin_ssh_key {
    username   = "danielmtz"
    public_key = var.ssh_public_key
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

  # Cloud-Init: Automated Docker + Tailscale + 2GB Swap setup
  user_data = base64encode(<<-EOT
    #cloud-config
    runcmd:
      - apt-get update
      - apt-get install -y apt-transport-https ca-certificates curl software-properties-common git
      - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | apt-key add -
      - add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu jammy stable"
      - apt-get update
      - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
      - systemctl enable docker
      - systemctl start docker
      - usermod -aG docker danielmtz
      - curl -fsSL https://tailscale.com/install.sh | sh
      - fallocate -l 2G /swapfile
      - chmod 600 /swapfile
      - mkswap /swapfile
      - swapon /swapfile
      - echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
      - mkdir -p /app
      - git clone ${var.github_repo_url} /app
      - chown -R danielmtz:danielmtz /app
    EOT
  )
}

output "azure_vm_public_ip" {
  value = azurerm_public_ip.main.ip_address
}
