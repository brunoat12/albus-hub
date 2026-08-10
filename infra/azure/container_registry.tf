resource "azurerm_container_registry" "app" {
  name                = replace("acr${var.project_name}fiap2026${var.environment}", "-", "")
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  sku           = "Basic"
  admin_enabled = true

  tags = local.common_tags
}
