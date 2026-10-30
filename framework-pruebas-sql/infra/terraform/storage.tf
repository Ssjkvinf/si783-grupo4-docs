############################################################
# Almacenamiento de las copias de seguridad de la SQLite
#   - Cuenta Standard LRS (redundancia local: la más barata; sin copia en otra región).
#   - Contenedor PRIVADO (sin acceso anónimo), TLS 1.2 como mínimo.
#   - Versionado + papelera de eliminación (7 días) frente a borrados accidentales.
#   - Política de ciclo de vida: elimina las copias a los `backup_retention_days` días.
# Permiso para escribir copias (se asigna a mano; ver docs/operacion-fase3.md):
#   rol «Storage Blob Data Contributor» sobre esta cuenta o contenedor para la identidad del workflow.
############################################################

resource "azurerm_storage_account" "backups" {
  count = var.create_backup_storage && local.has_resource_group ? 1 : 0

  name                = var.backup_storage_account_name
  resource_group_name = local.support_resource_group_name
  location            = var.backup_location != "" ? var.backup_location : local.support_location

  account_kind             = "StorageV2"
  account_tier             = "Standard"
  account_replication_type = "LRS"
  access_tier              = "Cool"

  min_tls_version                 = "TLS1_2"
  https_traffic_only_enabled      = true
  allow_nested_items_to_be_public = false

  blob_properties {
    versioning_enabled = true

    delete_retention_policy {
      days = 7
    }

    container_delete_retention_policy {
      days = 7
    }
  }

  tags = var.tags
}

resource "azurerm_storage_container" "backups" {
  count = length(azurerm_storage_account.backups) > 0 ? 1 : 0

  name                  = var.backup_container_name
  storage_account_id    = azurerm_storage_account.backups[0].id
  container_access_type = "private"
}

resource "azurerm_storage_management_policy" "backups" {
  count = length(azurerm_storage_account.backups) > 0 ? 1 : 0

  storage_account_id = azurerm_storage_account.backups[0].id

  rule {
    name    = "eliminar-copias-antiguas"
    enabled = true

    filters {
      blob_types   = ["blockBlob"]
      prefix_match = ["${var.backup_container_name}/"]
    }

    actions {
      base_blob {
        delete_after_days_since_modification_greater_than = var.backup_retention_days
      }
      version {
        delete_after_days_since_creation = var.backup_retention_days
      }
    }
  }
}
