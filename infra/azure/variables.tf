variable "environment" {
  description = "Ambiente da infraestrutura."
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Região principal dos recursos Azure."
  type        = string
  default     = "eastus2"
}

variable "project_name" {
  description = "Nome do projeto."
  type        = string
  default     = "albus-hub"
}

variable "mysql_admin_username" {
  description = "Usuário administrador do Azure Database for MySQL."
  type        = string
  default     = "albusadmin"
}

variable "mysql_admin_password" {
  description = "Senha do administrador do Azure Database for MySQL."
  type        = string
  sensitive   = true
}

