resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  sku               = "PerGB2018"
  retention_in_days = 30
  daily_quota_gb    = 0.5

  tags = local.common_tags
}

resource "azurerm_application_insights" "main" {
  name                = "appi-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  application_type = "web"
  workspace_id     = azurerm_log_analytics_workspace.main.id

  daily_data_cap_in_gb = 1

  tags = local.common_tags
}
