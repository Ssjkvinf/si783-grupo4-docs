terraform {
  required_version = ">= 1.9.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
  }

  # Backend remoto en Azure Storage. La configuración se pasa al ejecutar `terraform init`
  # con -backend-config (la hace el workflow infra.yml); aquí no hay nombres ni claves.
  # Para validar sin Azure: terraform init -backend=false
  backend "azurerm" {}
}
