############################################################
# Recursos EXISTENTES (solo lectura)
# Un data source nunca crea, modifica ni reemplaza el recurso. Si el nombre no existe, `plan` falla.
############################################################

data "azurerm_resource_group" "existing" {
  count = var.use_existing_vm ? 1 : 0
  name  = var.existing_resource_group_name
}

data "azurerm_virtual_machine" "existing" {
  count               = var.use_existing_vm ? 1 : 0
  name                = var.existing_vm_name
  resource_group_name = data.azurerm_resource_group.existing[0].name
}

locals {
  # Hay un grupo de recursos donde crear los recursos de apoyo solo en uno de los dos modos.
  has_resource_group = var.use_existing_vm || var.create_new_vm

  # Grupo de recursos y región de los recursos de apoyo.
  support_resource_group_name = var.use_existing_vm ? data.azurerm_resource_group.existing[0].name : (var.create_new_vm ? azurerm_resource_group.new[0].name : "")
  support_location            = var.use_existing_vm ? data.azurerm_resource_group.existing[0].location : (var.create_new_vm ? azurerm_resource_group.new[0].location : var.new_vm_location)
  support_resource_group_id   = var.use_existing_vm ? data.azurerm_resource_group.existing[0].id : (var.create_new_vm ? azurerm_resource_group.new[0].id : "")
}
