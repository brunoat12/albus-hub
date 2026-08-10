resource "azurerm_container_group" "app" {
  name                = "aci-${local.name_prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  os_type         = "Linux"
  ip_address_type = "Public"

  dns_name_label              = "albus-hub-${var.environment}-fiap2026"
  dns_name_label_reuse_policy = "ResourceGroupReuse"

  restart_policy = "Always"

  exposed_port {
    port     = 8501
    protocol = "TCP"
  }

  container {
    name  = "albus-hub"
    image = "${azurerm_container_registry.app.login_server}/albus-hub:sprint3"

    cpu    = 1
    memory = 2

    ports {
      port     = 8501
      protocol = "TCP"
    }

    environment_variables = {
      APP_ENV        = "azure"
      CLOUD_PROVIDER = "azure"
    }
  }

  image_registry_credential {
    server   = azurerm_container_registry.app.login_server
    username = azurerm_container_registry.app.admin_username
    password = azurerm_container_registry.app.admin_password
  }

  diagnostics {
    log_analytics {
      workspace_id  = azurerm_log_analytics_workspace.main.workspace_id
      workspace_key = azurerm_log_analytics_workspace.main.primary_shared_key
    }
  }

  tags = local.common_tags
}
