# Autenticación: variables de entorno ARM_CLIENT_ID, ARM_CLIENT_SECRET, ARM_TENANT_ID y
# ARM_SUBSCRIPTION_ID (en GitHub: secretos con esos nombres). No hay credenciales en el código.
provider "azurerm" {
  features {}

  subscription_id = var.subscription_id

  # No intentar registrar proveedores de recursos (requiere permisos amplios).
  # Microsoft.Storage, Microsoft.Network y Microsoft.Compute suelen estar ya registrados.
  resource_provider_registrations = "none"
}
