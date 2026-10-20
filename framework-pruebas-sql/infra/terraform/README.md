# Terraform del proyecto (Fase 3)

Guía completa: [`docs/operacion-fase3.md`](../../docs/operacion-fase3.md). Aquí solo lo esencial.

**La VM de Azure ya existe y no la gestiona Terraform.** Por defecto (`use_existing_vm = true`) se **lee** con data sources y Terraform añade solo recursos de apoyo:

| Recurso | Para qué | Cuándo se crea |
| --- | --- | --- |
| `azurerm_storage_account.backups` + contenedor privado + política de ciclo de vida | Guardar las copias de la SQLite con retención | `create_backup_storage = true` (por defecto) |
| `azurerm_consumption_budget_resource_group.monthly` | Alertas por correo (no limita el gasto) | `budget_amount > 0` y hay correos |
| `vm_new.tf` (VM, red, NSG, IP…) | Reproducir el entorno desde cero | **Nunca por defecto**: `create_new_vm = true` + `use_existing_vm = false` + `confirm_create_new_vm = "CREATE-NEW-VM"` |

Un plan con la configuración por defecto debe mostrar **3 creaciones y ningún cambio, eliminación ni reemplazo**.

## Valores que debe aportar quien ejecute (no hay valores por defecto ni en el repositorio)

`subscription_id`, `existing_resource_group_name`, `existing_vm_name`, `backup_storage_account_name` (y opcionalmente `existing_vm_size`). En GitHub llegan por variables y secretos (ver el manual); en local, con `TF_VAR_...` o `-var`, **nunca** en un archivo versionado (`*.tfvars` está en `.gitignore`).

## Validar sin Azure

```bash
terraform fmt -check -recursive
terraform init -backend=false      # descarga el proveedor azurerm; no usa credenciales
terraform validate
```

`-backend=false` no puede ejecutar `plan`: para un plan real hace falta el backend remoto y credenciales (lo hace el flujo `infra.yml`).

## Autenticación y estado

Credenciales: variables de entorno `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`. Estado: backend `azurerm` con configuración parcial (`terraform init -backend-config=...`), clave `framework-pruebas-sql.tfstate`.

El archivo `.terraform.lock.hcl` no se versiona todavía: el generado en Windows solo trae sumas de verificación de Windows y fallaría en el runner de Linux. Cuando exista un `init` en GitHub, generen el lock multiplataforma con `terraform providers lock -platform=linux_amd64 -platform=windows_amd64` y súbanlo.
