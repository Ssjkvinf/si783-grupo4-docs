output "modo" {
  description = "Modo de la configuración."
  value       = var.use_existing_vm ? "VM existente (solo lectura)" : (var.create_new_vm ? "VM nueva" : "sin VM")
}

output "vm_existente" {
  description = "Datos de la VM existente leídos de Azure (no gestionada por Terraform)."
  value = var.use_existing_vm ? {
    nombre            = data.azurerm_virtual_machine.existing[0].name
    grupo_de_recursos = data.azurerm_virtual_machine.existing[0].resource_group_name
    region            = data.azurerm_virtual_machine.existing[0].location
    estado            = data.azurerm_virtual_machine.existing[0].power_state
    ip_publica        = data.azurerm_virtual_machine.existing[0].public_ip_address
  } : null
}

output "almacenamiento_de_copias" {
  description = "Cuenta y contenedor de las copias (si se crean)."
  value = length(azurerm_storage_account.backups) > 0 ? {
    cuenta     = azurerm_storage_account.backups[0].name
    contenedor = var.backup_container_name
    retencion  = "${var.backup_retention_days} días"
  } : null
}

output "vm_nueva_ip_publica" {
  description = "IP pública de la VM nueva (solo en modo create_new_vm)."
  value       = length(azurerm_public_ip.new) > 0 ? azurerm_public_ip.new[0].ip_address : null
}
