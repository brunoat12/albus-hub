output "resource_group_name" {
  description = "Nome do Resource Group principal."
  value       = azurerm_resource_group.main.name
}

output "resource_group_location" {
  description = "Região do Resource Group principal."
  value       = azurerm_resource_group.main.location
}

output "virtual_network_name" {
  description = "Nome da Virtual Network principal."
  value       = azurerm_virtual_network.main.name
}

output "app_subnet_name" {
  description = "Nome da subnet destinada à aplicação."
  value       = azurerm_subnet.app.name
}


output "storage_account_name" {
  description = "Nome da Storage Account do Data Lake."
  value       = azurerm_storage_account.data_lake.name
}

output "storage_containers" {
  description = "Containers principais do Data Lake."
  value = [
    azurerm_storage_container.raw.name,
    azurerm_storage_container.trusted.name,
    azurerm_storage_container.gold.name,
    azurerm_storage_container.exports.name,
    azurerm_storage_container.backup.name,
  ]
}

output "mysql_server_name" {
  description = "Nome do Azure Database for MySQL Flexible Server."
  value       = azurerm_mysql_flexible_server.main.name
}

output "mysql_database_name" {
  description = "Nome do banco principal do Albus-Hub."
  value       = azurerm_mysql_flexible_database.main.name
}

output "mysql_fqdn" {
  description = "FQDN privado do servidor MySQL."
  value       = azurerm_mysql_flexible_server.main.fqdn
}


output "data_factory_name" {
  description = "Nome do Azure Data Factory."
  value       = azurerm_data_factory.main.name
}

output "data_factory_principal_id" {
  description = "Principal ID da Managed Identity do Data Factory."
  value       = azurerm_data_factory.main.identity[0].principal_id
}
output "container_registry_name" {
  description = "Nome do Azure Container Registry do Albus-Hub."
  value       = azurerm_container_registry.app.name
}

output "container_registry_login_server" {
  description = "Login server do Azure Container Registry."
  value       = azurerm_container_registry.app.login_server
}

output "log_analytics_workspace_name" {
  description = "Nome do Log Analytics Workspace usado pelo Azure Monitor."
  value       = azurerm_log_analytics_workspace.main.name
}

output "application_insights_name" {
  description = "Nome do Application Insights da aplicação."
  value       = azurerm_application_insights.main.name
}

output "container_instance_name" {
  description = "Nome do Azure Container Instance do Albus-Hub."
  value       = azurerm_container_group.app.name
}

output "container_instance_fqdn" {
  description = "FQDN público do dashboard Streamlit."
  value       = azurerm_container_group.app.fqdn
}

output "container_instance_ip_address" {
  description = "Endereço IP público do Azure Container Instance."
  value       = azurerm_container_group.app.ip_address
}
