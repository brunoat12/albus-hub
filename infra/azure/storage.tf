resource "azurerm_storage_account" "data_lake" {
  name                     = "stcalbushubdev"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  account_kind             = "StorageV2"

  is_hns_enabled             = true
  https_traffic_only_enabled = true

  min_tls_version = "TLS1_2"

  tags = local.common_tags
}

resource "azurerm_storage_container" "raw" {
  name                  = "raw"
  storage_account_id    = azurerm_storage_account.data_lake.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "trusted" {
  name                  = "trusted"
  storage_account_id    = azurerm_storage_account.data_lake.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "gold" {
  name                  = "gold"
  storage_account_id    = azurerm_storage_account.data_lake.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "exports" {
  name                  = "exports"
  storage_account_id    = azurerm_storage_account.data_lake.id
  container_access_type = "private"
}

resource "azurerm_storage_container" "backup" {
  name                  = "backup"
  storage_account_id    = azurerm_storage_account.data_lake.id
  container_access_type = "private"
}