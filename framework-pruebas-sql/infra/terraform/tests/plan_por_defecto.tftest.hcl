# Pruebas de Terraform SIN Azure ni credenciales: el proveedor azurerm se reemplaza por un simulado (mock_provider).
# Comprueban qué haría un `plan` con la configuración por defecto: solo LEER la VM existente y crear recursos de apoyo.
# Ejecutar: terraform init -backend=false && terraform test
# Los identificadores son ficticios (ceros); no corresponden a ninguna suscripción real.

mock_provider "azurerm" {
  mock_data "azurerm_resource_group" {
    defaults = {
      name     = "rg-existente-ficticio"
      location = "eastus2"
      id       = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-existente-ficticio"
    }
  }

  mock_data "azurerm_virtual_machine" {
    defaults = {
      name                = "vm-existente-ficticia"
      location            = "eastus2"
      resource_group_name = "rg-existente-ficticio"
      power_state         = "running"
      public_ip_address   = "203.0.113.10"
    }
  }
}

variables {
  subscription_id              = "00000000-0000-0000-0000-000000000000"
  existing_resource_group_name = "rg-existente-ficticio"
  existing_vm_name             = "vm-existente-ficticia"
  backup_storage_account_name  = "fwbackupsficticio"
}

run "por_defecto_lee_la_vm_y_solo_crea_el_almacenamiento_de_copias" {
  command = plan

  assert {
    condition     = length(data.azurerm_virtual_machine.existing) == 1 && length(data.azurerm_resource_group.existing) == 1
    error_message = "La VM y su grupo de recursos deben LEERSE con data sources."
  }
  assert {
    condition = (length(azurerm_resource_group.new) + length(azurerm_virtual_network.new) + length(azurerm_subnet.new)
      + length(azurerm_public_ip.new) + length(azurerm_network_security_group.new) + length(azurerm_network_interface.new)
    + length(azurerm_linux_virtual_machine.new)) == 0
    error_message = "Con la configuración por defecto no debe planearse ninguna VM, red, IP ni grupo de recursos."
  }
  assert {
    condition     = length(azurerm_storage_account.backups) == 1 && length(azurerm_storage_container.backups) == 1 && length(azurerm_storage_management_policy.backups) == 1
    error_message = "Debe crearse la cuenta de copias, su contenedor y la política de retención."
  }
  assert {
    condition     = azurerm_storage_account.backups[0].resource_group_name == "rg-existente-ficticio"
    error_message = "El almacenamiento de copias debe ir al grupo de recursos EXISTENTE (leído), no a uno nuevo."
  }
  assert {
    condition     = azurerm_storage_container.backups[0].container_access_type == "private" && azurerm_storage_account.backups[0].allow_nested_items_to_be_public == false
    error_message = "Las copias nunca deben quedar públicas."
  }
  assert {
    condition     = length(azurerm_consumption_budget_resource_group.monthly) == 0
    error_message = "Sin importe ni correos no se crea presupuesto."
  }
}

run "presupuesto_opcional_sobre_el_grupo_existente" {
  command = plan

  variables {
    budget_amount       = 20
    budget_alert_emails = ["equipo@example.com"]
  }

  assert {
    condition     = length(azurerm_consumption_budget_resource_group.monthly) == 1
    error_message = "Con importe y correo debe planearse el presupuesto."
  }
  assert {
    condition     = length(azurerm_linux_virtual_machine.new) == 0
    error_message = "El presupuesto no debe traer una VM."
  }
}

run "no_se_mezcla_la_vm_existente_con_una_nueva" {
  command = plan

  variables {
    create_new_vm = true
  }

  expect_failures = [var.create_new_vm]
}

run "una_vm_nueva_exige_la_confirmacion_explicita" {
  command = plan

  variables {
    use_existing_vm = false
    create_new_vm   = true
    # Llave PÚBLICA desechable generada solo para esta prueba (la privada se borró al crearla): no da acceso a nada.
    new_vm_ssh_public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFnQP3ZmV3mzCavlDLMs05frUxV1zNdhgsaYJMxaMnCL prueba-terraform-desechable"
  }

  expect_failures = [var.confirm_create_new_vm]
}
