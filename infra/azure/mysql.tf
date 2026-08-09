resource "azurerm_mysql_flexible_server" "main" {
  name                = "mysql-albushub-dev-2026"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  administrator_login    = var.mysql_admin_username
  administrator_password = var.mysql_admin_password

  sku_name = "B_Standard_B1ms"
  version  = "8.0.21"

  public_network_access = "Enabled"

  backup_retention_days        = 7
  geo_redundant_backup_enabled = false

  storage {
    size_gb           = 20
    auto_grow_enabled = true
  }

  tags = local.common_tags
}

resource "azurerm_mysql_flexible_server_firewall_rule" "allow_azure_services" {
  name                = "AllowAzureServices"
  resource_group_name = azurerm_resource_group.main.name
  server_name         = azurerm_mysql_flexible_server.main.name

  start_ip_address = "0.0.0.0"
  end_ip_address   = "0.0.0.0"
}

resource "azurerm_mysql_flexible_database" "main" {
  name                = "albus_hub"
  resource_group_name = azurerm_resource_group.main.name
  server_name         = azurerm_mysql_flexible_server.main.name

  charset   = "utf8mb4"
  collation = "utf8mb4_unicode_ci"

  lifecycle {
    replace_triggered_by = [
      azurerm_mysql_flexible_server.main
    ]
  }
}