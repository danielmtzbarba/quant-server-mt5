#!/bin/bash
set -e

# Extract variables from terraform.tfvars if not provided in environment
get_tf_var() {
    local var_name=$1
    local env_val=$(eval echo "\$$var_name")
    if [ -n "$env_val" ]; then
        echo "$env_val"
    else
        grep -oP "${var_name}\s*=\s*\"\K[^\"]+" terraform.tfvars || echo ""
    fi
}

AZURE_SUBSCRIPTION_ID=$(get_tf_var "AZURE_SUBSCRIPTION_ID")
AZURE_RESOURCE_GROUP=$(get_tf_var "AZURE_RESOURCE_GROUP")
AZURE_LOCATION=$(get_tf_var "AZURE_LOCATION")
AZURE_VM_SIZE=$(get_tf_var "AZURE_VM_SIZE")

# Variable check
if [ -z "$AZURE_SUBSCRIPTION_ID" ] || [ -z "$AZURE_RESOURCE_GROUP" ]; then
    echo "Error: AZURE_SUBSCRIPTION_ID and AZURE_RESOURCE_GROUP must be set (either in env or terraform.tfvars)."
    exit 1
fi

BASE_ID="/subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP}/providers/Microsoft.Network"

echo "Attempting to import existing infrastructure to avoid collisions..."

# Function to safely import
safe_import() {
    local address=$1
    local id=$2
    echo "Importing $address..."
    terraform import \
        -var="AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID" \
        -var="AZURE_CLIENT_ID=$AZURE_CLIENT_ID" \
        -var="AZURE_CLIENT_SECRET=$AZURE_CLIENT_SECRET" \
        -var="AZURE_TENANT_ID=$AZURE_TENANT_ID" \
        -var="AZURE_RESOURCE_GROUP=$AZURE_RESOURCE_GROUP" \
        -var="AZURE_LOCATION=$AZURE_LOCATION" \
        -var="AZURE_VM_SIZE=$AZURE_VM_SIZE" \
        -var="ADMIN_IP=$ADMIN_IP" \
        -var="SSH_PUBLIC_KEY=$SSH_PUBLIC_KEY" \
        -var="GITHUB_REPO_URL=$GITHUB_REPO_URL" \
        -var="TAILSCALE_AUTH_KEY=$TAILSCALE_AUTH_KEY" \
        "$address" "$id" || echo "$address already managed."
}

# 1. Resource Group
terraform import \
    -var="AZURE_SUBSCRIPTION_ID=$AZURE_SUBSCRIPTION_ID" \
    -var="AZURE_CLIENT_ID=$AZURE_CLIENT_ID" \
    -var="AZURE_CLIENT_SECRET=$AZURE_CLIENT_SECRET" \
    -var="AZURE_TENANT_ID=$AZURE_TENANT_ID" \
    -var="AZURE_RESOURCE_GROUP=$AZURE_RESOURCE_GROUP" \
    -var="AZURE_LOCATION=$AZURE_LOCATION" \
    -var="AZURE_VM_SIZE=$AZURE_VM_SIZE" \
    -var="ADMIN_IP=$ADMIN_IP" \
    -var="SSH_PUBLIC_KEY=$SSH_PUBLIC_KEY" \
    -var="GITHUB_REPO_URL=$GITHUB_REPO_URL" \
    -var="TAILSCALE_AUTH_KEY=$TAILSCALE_AUTH_KEY" \
    azurerm_resource_group.main /subscriptions/${AZURE_SUBSCRIPTION_ID}/resourceGroups/${AZURE_RESOURCE_GROUP} || echo "RG already managed."

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
