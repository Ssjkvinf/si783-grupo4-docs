############################################################
# Modo de uso
#   use_existing_vm = true  (por defecto): la VM y su grupo de recursos YA EXISTEN. Solo se leen con
#                           data sources (no se crean ni se reemplazan) y Terraform añade recursos de apoyo
#                           (almacenamiento de copias de seguridad y, opcionalmente, un presupuesto).
#   create_new_vm   = true  (excepcional): crea una VM nueva desde cero en un grupo de recursos nuevo.
#                           Requiere una confirmación explícita y no puede combinarse con use_existing_vm.
############################################################

variable "subscription_id" {
  description = "ID de la suscripción de Azure. Lo aporta el secreto/variable de GitHub; no se escribe en el repositorio."
  type        = string
}

variable "use_existing_vm" {
  description = "true: usar la VM existente (solo lectura). false: no leer ninguna VM existente."
  type        = bool
  default     = true
}

variable "existing_resource_group_name" {
  description = "Nombre del grupo de recursos que YA contiene la VM (se obtiene del portal de Azure; ver docs/operacion-fase3.md)."
  type        = string
  default     = ""

  validation {
    condition     = !var.use_existing_vm || length(trimspace(var.existing_resource_group_name)) > 0
    error_message = "Con use_existing_vm = true debe indicar existing_resource_group_name."
  }
}

variable "existing_vm_name" {
  description = "Nombre de la VM existente (solo lectura)."
  type        = string
  default     = ""

  validation {
    condition     = !var.use_existing_vm || length(trimspace(var.existing_vm_name)) > 0
    error_message = "Con use_existing_vm = true debe indicar existing_vm_name."
  }
}

variable "existing_vm_size" {
  description = "Tamaño de la VM existente (el que muestra el portal). Solo se usa para la ESTIMACIÓN de costos del reporte; el data source no lo expone. Vacío = no se estima."
  type        = string
  default     = ""
}

############################ Almacenamiento de copias de seguridad ############################

variable "create_backup_storage" {
  description = "Crear la cuenta de almacenamiento y el contenedor privado para las copias de la SQLite."
  type        = bool
  default     = true
}

variable "backup_storage_account_name" {
  description = "Nombre de la cuenta de almacenamiento (único en todo Azure, 3-24 caracteres, minúsculas y números)."
  type        = string
  default     = ""

  validation {
    condition     = !var.create_backup_storage || can(regex("^[a-z0-9]{3,24}$", var.backup_storage_account_name))
    error_message = "backup_storage_account_name debe tener 3-24 caracteres, solo minúsculas y números."
  }
}

variable "backup_location" {
  description = "Región de la cuenta de copias. Vacío = la del grupo de recursos. Las suscripciones de estudiante solo permiten algunas regiones (p. ej. la de la VM)."
  type        = string
  default     = ""
}

variable "backup_container_name" {
  description = "Contenedor privado de blobs para las copias."
  type        = string
  default     = "sqlite-backups"
}

variable "backup_retention_days" {
  description = "Días que se conservan las copias antes de que la política de ciclo de vida las elimine."
  type        = number
  default     = 30

  validation {
    condition     = var.backup_retention_days >= 7 && var.backup_retention_days <= 365
    error_message = "backup_retention_days debe estar entre 7 y 365."
  }
}

############################ Presupuesto (alerta de costos) ############################

variable "budget_amount" {
  description = "Presupuesto mensual del grupo de recursos, en la moneda de facturación de la suscripción. 0 = no crear presupuesto."
  type        = number
  default     = 0
}

variable "budget_alert_emails" {
  description = "Correos que reciben las alertas del presupuesto (vacío = no crear presupuesto)."
  type        = list(string)
  default     = []
}

variable "budget_start_date" {
  description = "Primer día de un mes (YYYY-MM-01T00:00:00Z) desde el que rige el presupuesto."
  type        = string
  default     = "2026-11-01T00:00:00Z"
}

variable "tags" {
  description = "Etiquetas para los recursos que crea Terraform."
  type        = map(string)
  default = {
    proyecto = "framework-pruebas-sql"
    curso    = "SI783"
    gestion  = "terraform"
  }
}

############################ VM nueva (modo excepcional) ############################

variable "create_new_vm" {
  description = "Crear una VM NUEVA desde cero. Déjelo en false para trabajar con la VM existente."
  type        = bool
  default     = false

  validation {
    condition     = !(var.create_new_vm && var.use_existing_vm)
    error_message = "create_new_vm = true exige use_existing_vm = false: no se mezclan la VM existente y una nueva."
  }
}

variable "confirm_create_new_vm" {
  description = "Confirmación explícita para crear una VM nueva: debe ser exactamente CREATE-NEW-VM."
  type        = string
  default     = ""

  validation {
    condition     = !var.create_new_vm || var.confirm_create_new_vm == "CREATE-NEW-VM"
    error_message = "Para crear una VM nueva establezca confirm_create_new_vm = \"CREATE-NEW-VM\"."
  }
}

variable "new_vm_resource_group_name" {
  description = "Grupo de recursos NUEVO para la VM nueva."
  type        = string
  default     = "rg-framework-sql-nuevo"
}

variable "new_vm_location" {
  description = "Región de Azure de la VM nueva."
  type        = string
  default     = "eastus2"
}

variable "new_vm_size" {
  description = "Tamaño de la VM nueva. Oracle Free necesita al menos 2 GB de RAM; Standard_B2s tiene 4 GiB."
  type        = string
  default     = "Standard_B2s"
}

variable "new_vm_os_disk_gb" {
  description = "Tamaño del disco del sistema de la VM nueva (GB)."
  type        = number
  default     = 64
}

variable "new_vm_admin_username" {
  description = "Usuario administrador (solo autenticación por llave SSH)."
  type        = string
  default     = "azureuser"
}

variable "new_vm_ssh_public_key" {
  description = "Llave PÚBLICA SSH (p. ej. el contenido de id_ed25519.pub). Nunca la privada."
  type        = string
  default     = ""

  validation {
    condition     = !var.create_new_vm || length(trimspace(var.new_vm_ssh_public_key)) > 0
    error_message = "Con create_new_vm = true indique new_vm_ssh_public_key (llave pública)."
  }
}

variable "new_vm_ssh_allowed_cidrs" {
  description = "Rangos CIDR autorizados para SSH (22) a la VM nueva. Vacío = no se abre SSH. 0.0.0.0/0 abre SSH a todo Internet (solo si se asume ese riesgo)."
  type        = list(string)
  default     = []
}

variable "new_vm_domain_name_label" {
  description = "Etiqueta DNS de la IP pública de la VM nueva (<etiqueta>.<región>.cloudapp.azure.com)."
  type        = string
  default     = ""
}
