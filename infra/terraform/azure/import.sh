#!/bin/bash
set -e

# Variable check
if [ -z "$AZURE_SUBSCRIPTION_ID" ] || [ -z "$AZURE_RESOURCE_GROUP" ]; then
    echo "Error: AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP must be set."
    exit 1
fi

BASE_ID="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}/providers/Microsoft.Network"

echo "Attempting to import existing infrastructure to avoid collisions..."

# Fetch current state once to avoid multiple slow calls
echo "Checking current Terraform state..."
CURRENT_STATE=$(terraform state list 2>/dev/null || echo "")

# Define common variables as an array for safe evaluation
VARS=(
    -var="AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID"
    -var="AZURE_CLIENT_ID=$AZURE_CLIENT_ID"
    -var="AZURE_CLIENT_SECRET=$AZURE_CLIENT_SECRET"
    -var="AZURE_TENANT_ID=$AZURE_TENANT_ID"
    -var="AZURE_RESOURCE_GROUP=$AZURE_RESOURCE_GROUP"
    -var="AZURE_LOCATION=$AZURE_LOCATION"
    -var="AZURE_VM_SIZE=$AZURE_VM_SIZE"
    -var="ADMIN_IP=$ADMIN_IP"
    -var="SSH_PUBLIC_KEY=$SSH_PUBLIC_KEY"
    -var="GITHUB_REPO_URL=$GITHUB_REPO_URL"
    -var="TAILSCALE_AUTH_KEY=$TAILSCALE_AUTH_KEY"
)

# Function to safely import
safe_import() {
    local address=$1
    local id=$2

    if echo "$CURRENT_STATE" | grep -q "^${address}$"; then
        echo "✓ $address already managed."
    else
        echo "➜ Importing $address..."
        terraform import "${VARS[@]}" "$address" "$id"
    fi
}

# 1. Resource Group
safe_import "azurerm_resource_group.main" "/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}"

# 2. VNET
safe_import "azurerm_virtual_network.main" "$BASE_ID/virtualNetworks/trading-network"

# 3. SUBNET
safe_import "azurerm_subnet.internal" "$BASE_ID/virtualNetworks/trading-network/subnets/trading-subnet"

# 4. NSG
safe_import "azurerm_network_security_group.main" "$BASE_ID/networkSecurityGroups/trading-nsg"

# 5. PUBLIC IP
safe_import "azurerm_public_ip.main" "$BASE_ID/publicIPAddresses/mt5-public-ip"

# 6. NIC
safe_import "azurerm_network_interface.main" "$BASE_ID/networkInterfaces/mt5-nic"

# 7. NIC-NSG Association (Join format)
safe_import "azurerm_network_interface_security_group_association.main" "$BASE_ID/networkInterfaces/mt5-nic|/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}/providers/Microsoft.Network/networkSecurityGroups/trading-nsg"
