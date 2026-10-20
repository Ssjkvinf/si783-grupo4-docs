# Manual operativo — Fase 3: infraestructura, base de datos, copias, release y despliegue

Para **Kevin y Gerald**. Explica qué automatiza cada flujo de GitHub Actions, qué hay que configurar (nombres de secretos y variables, **nunca sus valores**), en qué orden ejecutarlo y qué evidencias guardar.

## 0. Cómo leer el estado de cada cosa

| Etiqueta | Significa |
| --- | --- |
| **Preparado localmente** | Los archivos existen en el repositorio local. No implica que funcionen en la nube. |
| **Validado localmente** | Se ejecutó una comprobación en este equipo (no en GitHub ni en Azure) y se anotó su resultado real. |
| **Comprobado en GitHub/Azure** | Se ejecutó el flujo real en GitHub Actions o contra Azure. **Nada de esta fase está en este estado todavía**: solo ustedes pueden hacerlo tras revisar y subir los cambios. |

### Estado al cerrar la Fase 3

| Componente | Preparado | Validado localmente | Comprobado en GitHub/Azure |
| --- | --- | --- | --- |
| Terraform (VM existente en modo lectura + almacenamiento de copias + presupuesto opcional) | Sí | `fmt` ✔, `init -backend=false` ✔ (proveedor azurerm 4.81.0 desde caché local), `validate` ✔, 4 reglas de las variables probadas con `plan` (fallan con mensaje claro) ✔ | No. **No hay plan real**: exige credenciales y los datos de su VM. |
| Reporte de costos | Sí | Con un plan **sintético** y los precios de lista reales de la API pública de Azure ✔; si la API falla no inventa cifras ✔ | No (el gasto real exige permisos de Cost Management) |
| Reporte de pruebas (JUnit → Markdown) | Sí | ✔ (las omitidas no cuentan como aprobadas) | No |
| Alembic (SQLite interna) | Sí | Reporte con 2 ejecuciones sobre una SQLite desechable ✔ (idempotente, sin diferencias modelos↔migraciones) | No |
| Liquibase (objetos Oracle de la demostración) | Sí | `update-sql` sin base ✔ (Liquibase 4.33.0 real); **2 ejecuciones reales** contra **H2 en modo Oracle** ✔ (la 2.ª aplica 0); escenario de adopción (tabla ya existente → `MARK_RAN`) ✔ | No. **No se ejecutó contra un Oracle real**: Docker Desktop dejó de arrancar contenedores (ver §9). |
| Copia consistente de la SQLite + restauración aislada | Sí | pytest: 15 copias con un escritor concurrente ✔, restauración aislada ✔, copia alterada detectada ✔, la base activa no cambia ✔ | No |
| `backup_vm.sh` (copia dentro de Docker en la VM) | Sí | Solo sintaxis ✔ y revisión estática; **no se ejecutó con Docker** | No |
| Subida de la copia a Azure Blob | Sí | No | No |
| Release (imagen en GHCR + release de GitHub) | Sí | `docker build` local ✔ (la imagen contiene los scripts de copia) | No |
| Despliegue y reversión en la VM | Sí | Sintaxis `bash -n` ✔ y revisión estática | No |
| Sintaxis de los workflows | Sí | YAML válido ✔ (PyYAML) y pruebas estáticas de seguridad ✔; **`actionlint` no se ejecutó** (necesita Docker) | No |

## 1. Qué hace cada flujo

| Flujo (`.github/workflows/`) | Cuándo corre | Qué toca | Qué produce |
| --- | --- | --- | --- |
| `tests.yml` | push / PR | Nada remoto | Reporte de pruebas (resumen + artefacto) |
| `infra.yml` | push/PR que tocan `infra/terraform`: **solo valida**. Manual: `validate`, `plan` o `apply` | `plan` **lee** Azure; `apply` crea recursos (tras aprobación) | Reporte del plan, reporte de costos **estimados**, reporte de pruebas |
| `db-objects.yml` | push/PR que tocan Alembic u Oracle; manual | Nada remoto (Oracle desechable dentro del runner) | Reporte de Alembic, reporte de Liquibase, pruebas contra Oracle |
| `backup.yml` | **Manual**; programado solo si `BACKUP_SCHEDULE_ENABLED=true` | La VM (lectura), Azure Blob (escritura) | Reporte de copia y de restauración verificada |
| `release.yml` | **Manual** | GHCR (publica imagen), GitHub (tag + release) | Imagen versionada, release, reporte de pruebas |
| `deploy.yml` | **Manual** (o desde `release.yml`) con **aprobación** | La VM (solo el servicio `api`) | Log, reporte JSON en la VM, prueba de salud |

Un `push` **nunca** despliega, publica ni cambia infraestructura. `apply`, `deploy` y la subida de copias exigen ejecución manual; `apply` y `deploy` además exigen que **otra persona apruebe** en un *Environment*.

## 2. Datos de Azure que ustedes deben obtener (no se inventaron)

Este repositorio **no contiene** el grupo de recursos, el nombre, el tamaño ni la IP de su VM (solo los documentos dicen «Azure», y el README, que usa Caddy y un dominio). Los comandos son para **que ustedes los ejecuten** en su cuenta; no se ejecutó ninguno.

```bash
az login
az account show --query "{suscripcion:id, tenant:tenantId}" -o table
az vm list -d -o table --query "[].{nombre:name, grupo:resourceGroup, tamano:hardwareProfile.vmSize, region:location, estado:powerState, ip:publicIps}"
az storage account list -o table --query "[].{cuenta:name, grupo:resourceGroup, region:location}"
```

Anoten: grupo de recursos de la VM, nombre de la VM, su tamaño (p. ej. `Standard_B2s`), región, IP/DNS público y la carpeta de la VM donde está `compose.yml` + `.env.production` (por el README, `infra/production`).

**Identidad para GitHub (service principal)** — mínimo privilegio, solo sobre el grupo de recursos de la VM:

```bash
az ad sp create-for-rbac --name "sp-framework-sql" --role Contributor \
  --scopes /subscriptions/<ID_SUSCRIPCION>/resourceGroups/<GRUPO_DE_LA_VM>
```

La salida contiene un secreto: cópienlo **directamente** a los secretos de GitHub y no lo peguen en chats, correos ni archivos. Si su cuenta universitaria no permite crear service principals, pidan al docente que lo cree.

Roles adicionales (Terraform no los asigna):

| Para qué | Rol | Alcance |
| --- | --- | --- |
| Guardar el estado de Terraform | Storage Blob Data Contributor (o acceso a la cuenta de estado) | El contenedor/cuenta de estado |
| Subir copias a Blob | **Storage Blob Data Contributor** | El contenedor de copias (se crea tras el `apply`) |
| Gasto real en el reporte (opcional) | Cost Management Reader | El grupo de recursos |

```bash
az role assignment create --assignee <APP_ID_DEL_SP> --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<ID>/resourceGroups/<GRUPO>/providers/Microsoft.Storage/storageAccounts/<CUENTA_DE_COPIAS>/blobServices/default/containers/sqlite-backups
```

**Estado remoto de Terraform:** necesitan un grupo de recursos + cuenta de almacenamiento + contenedor para el `.tfstate`. Si todavía existe el que usaron en el laboratorio anterior (el workflow `infra.yml` de ese repositorio usaba las variables `TFSTATE_RESOURCE_GROUP`, `TFSTATE_STORAGE_ACCOUNT` y `TFSTATE_CONTAINER`), pueden reutilizarlo: este proyecto guarda su estado con otra clave (`framework-pruebas-sql.tfstate`). **No se verificó que ese almacenamiento exista ni que el service principal nuevo tenga acceso.** Si no existe, créenlo una vez a mano (`az group create`, `az storage account create --sku Standard_LRS`, `az storage container create`).

## 3. Configurar GitHub (una vez)

*Settings → Environments → New environment*:

| Entorno | Revisores obligatorios («Required reviewers») | Para qué |
| --- | --- | --- |
| `azure-plan` | No | `plan` (solo lectura de Azure) |
| `azure-apply` | **Sí**, la otra persona del equipo (active «Prevent self-review») | `apply` |
| `azure-backup` | No | copia de la SQLite |
| `azure-production` | **Sí**, la otra persona del equipo | despliegue y reversión |

**Secretos** (*Environment secrets*; solo los nombres):

| Secreto | Entornos | Contenido |
| --- | --- | --- |
| `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` | `azure-plan`, `azure-apply`, `azure-backup` | Del service principal |
| `VM_HOST` | `azure-backup`, `azure-production` | IP o DNS de la VM |
| `VM_USER` | `azure-backup`, `azure-production` | Usuario SSH (debe poder usar Docker) |
| `VM_SSH_KEY` | `azure-backup`, `azure-production` | Llave **privada** de despliegue (dedicada; ver abajo) |
| `VM_SSH_KNOWN_HOSTS` | `azure-backup`, `azure-production` | Salida de `ssh-keyscan -t ed25519 <host>` |
| `GHCR_USER`, `GHCR_TOKEN` | `azure-production` | Solo si el paquete de GHCR es privado: usuario y token con `read:packages` |

**Variables** (*Variables*, no secretas):

| Variable | Dónde | Ejemplo / significado |
| --- | --- | --- |
| `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME` | repositorio | Los de su VM |
| `AZURE_VM_SIZE`, `AZURE_LOCATION` | repositorio | Para la **estimación** de costos (p. ej. tamaño del portal y `eastus2`) |
| `BACKUP_STORAGE_ACCOUNT` | repositorio | Nombre único global, 3-24 minúsculas/números (lo crea Terraform) |
| `BACKUP_CONTAINER` (opc.), `BACKUP_RETENTION_DAYS` (opc.) | repositorio | `sqlite-backups`, `30` |
| `TFSTATE_RESOURCE_GROUP`, `TFSTATE_STORAGE_ACCOUNT`, `TFSTATE_CONTAINER` | repositorio | Estado remoto |
| `VM_APP_DIR` | repositorio | Carpeta de la VM con `compose.yml` y `.env.production` |
| `VM_BACKUP_DIR` (opc.), `APP_DATA_VOLUME` (opc.) | repositorio | `/opt/framework/backups`, `framework_pruebas_sql_framework_data` |
| `APP_PUBLIC_URL` (opc.) | repositorio | URL pública sin barra final, para la prueba de salud externa |
| `COST_REAL_ENABLED`, `BACKUP_SCHEDULE_ENABLED` (opc.) | repositorio | `true` para activar el gasto real / la copia diaria |

**Llave SSH dedicada** (no reutilicen su llave personal):

```bash
ssh-keygen -t ed25519 -f deploy_key -C "github-actions-framework" -N ""
# 1) añada deploy_key.pub a ~/.ssh/authorized_keys del usuario de la VM
# 2) copie el CONTENIDO de deploy_key al secreto VM_SSH_KEY y borre el archivo local
ssh-keyscan -t ed25519 <IP_O_DNS_DE_LA_VM>      # salida -> secreto VM_SSH_KNOWN_HOSTS (compare la huella con la que ya conoce)
```

En la VM: `sudo mkdir -p /opt/framework/backups /opt/framework/releases && sudo chown -R "$USER" /opt/framework`.

*Settings → Actions → General*: Actions habilitadas y **Workflow permissions** = lectura (los flujos piden los permisos que necesitan). *Packages*: el flujo `release.yml` publica en GHCR con `GITHUB_TOKEN`. **Pregunten al docente si la organización permite Environments, Secrets y Packages**; en repositorios de organización suele requerir permisos de administrador.

## 4. Terraform (rúbrica: infraestructura + reporte de pruebas + reporte de costos)

**Qué crea la configuración por defecto:** nada que reemplace la VM. La VM y su grupo de recursos se **leen** con *data sources*. Terraform añade solo: una cuenta de almacenamiento (LRS, nivel Cool, TLS 1.2, sin acceso anónimo, versionado y papelera de 7 días), un contenedor privado y una política de ciclo de vida (borra copias a los `BACKUP_RETENTION_DAYS` días). Un presupuesto con alertas es opcional.

Un plan correcto para la configuración por defecto debe mostrar **3 creaciones** (cuenta, contenedor, política) y **0 modificaciones, eliminaciones o reemplazos**. Si ve algo distinto, no apruebe.

El modo «VM nueva» existe para reproducir el entorno desde cero, **no** para este proyecto: exige `use_existing_vm=false`, `create_new_vm=true` y `confirm_create_new_vm="CREATE-NEW-VM"`, y no se puede activar desde el workflow.

Pasos:
1. **Actions → Infraestructura (Terraform) → Run workflow → `validate`.** Sin secretos. Guarden la captura del resumen.
2. Configuren secretos y variables (§3) y ejecuten `plan`. El flujo se **detiene con un mensaje claro** si falta algo (no produce un plan falso).
3. Descarguen/lean los artefactos `reportes-terraform`: `reporte_plan.md` (qué cambia; **bloquea** eliminaciones, reemplazos y cualquier cambio de VM), `costos/cost_report.md` (**estimación**) y el reporte de pruebas.
4. Revisen con la lista del paso anterior. Solo entonces, `apply` con `confirm_apply = APPLY`: el flujo vuelve a planificar y **espera la aprobación** de la otra persona en `azure-apply`; aplica **el archivo de plan ya revisado**.
5. Asignen el rol de escritura sobre el contenedor de copias (§2).

**Costos — qué es estimación y qué es gasto real.** El reporte usa los **precios de lista** de la API pública «Azure Retail Prices» (730 h/mes, USD). **No es gasto real**: no incluye impuestos, créditos educativos, descuentos, tráfico saliente ni uso real, y un recurso «sin estimar» no cuesta cero. El **gasto real** solo aparece si activan `COST_REAL_ENABLED=true` y el service principal tiene *Cost Management Reader*; si no, el reporte dice «No disponible». La VM existente no la gestiona Terraform: su costo aparece aparte, como referencia, si definen `AZURE_VM_SIZE`.

**Adoptar la VM existente en el estado (opcional, solo si algún día quieren que Terraform la gestione):** no hace falta para esta fase. Si lo desean: escriban un recurso `azurerm_linux_virtual_machine` con `lifecycle { prevent_destroy = true; ignore_changes = all }` y ejecuten `terraform import 'azurerm_linux_virtual_machine.<nombre>' /subscriptions/<ID>/resourceGroups/<GRUPO>/providers/Microsoft.Compute/virtualMachines/<VM>`; revisen el `plan` hasta que no muestre cambios antes de quitar `ignore_changes`. **No se ejecutó ninguna importación.**

## 5. Objetos de base de datos — qué es de SQLite y qué es de Oracle

| | SQLite **interna** de la aplicación | Oracle de la **demostración** |
| --- | --- | --- |
| Contiene | proyectos, conexiones, casos, suites, historial | tabla `FRAMEWORK_TEST_ITEMS`, índice, vista y datos de ejemplo |
| Herramienta | **Alembic** (`alembic/`) | **Liquibase** (`infra/oracle/liquibase/`) |
| Cuándo se aplica | automáticamente al arrancar el contenedor (`start_production.sh`) | por el flujo `db-objects.yml` en un Oracle **desechable**; en una base real, a mano |
| Reporte | `reporte_alembic.md` | `reporte_liquibase.md` |

Es una decisión deliberada: Alembic ya versiona la SQLite y Liquibase se usa donde la rúbrica lo recomienda (los objetos Oracle). Pregunten al ingeniero si Alembic basta para la SQLite; no se reescribieron las migraciones.

`db-objects.yml` levanta un Oracle Free desechable (`gvenzl/oracle-free:23-slim-faststart`, imagen de la comunidad pensada para CI) con contraseñas efímeras, concede a `FRAMEWORK_TEST` los privilegios que Liquibase necesita (`infra/oracle/liquibase/grant_migration_privileges.sql`: `CREATE TABLE`, `CREATE VIEW`), aplica los changelogs **dos veces** (la 2.ª debe aplicar 0), genera el reporte, corre las pruebas de integración contra ese Oracle y descarta todo.

Contextos: `esquema` (tabla, índice, vista: seguro) y `demo` (borra y recarga los datos de ejemplo: **solo en un Oracle desechable**).

- Si el Oracle ya tiene la tabla (la creó `init/001_test_schema.sh`), el changeset 001 se **marca como ejecutado sin tocarla** (`MARK_RAN`). Esto se comprobó con Liquibase real sobre H2.
- El changeset 001 **no tiene rollback** a propósito: la tabla puede ser anterior y borrarla destruiría datos.
- Para aplicarlo a mano en la VM (nunca con el contexto `demo` si hay datos reales; primero concedan los privilegios como SYS): `docker run --rm --network framework_pruebas_sql_framework_net -e LIQUIBASE_COMMAND_URL=jdbc:oracle:thin:@//oracle_db:1521/FREEPDB1 -e LIQUIBASE_COMMAND_USERNAME=FRAMEWORK_TEST -e LIQUIBASE_COMMAND_PASSWORD -v <carpeta>/infra/oracle/liquibase:/liquibase/project:ro -w /liquibase/project liquibase/liquibase:4.33 --defaults-file=liquibase.properties update --contexts=esquema` con `LIQUIBASE_COMMAND_PASSWORD` exportada desde `.env.production` (no la escriban en la línea de comandos). **No se ejecutó.**
- La cuenta `FRAMEWORK_TEST` necesita `CREATE TABLE` para crear las tablas de control de Liquibase: eso amplía sus privilegios. Es aceptable en una base de demostración; para una base real usen una cuenta de migración distinta de la que usa la aplicación.

## 6. Copias de seguridad de la SQLite

**Por qué no basta `cp`:** mientras la aplicación escribe, copiar el archivo puede mezclar páginas de transacciones distintas. Se usa la **API de respaldo en línea de SQLite**, que toma una instantánea coherente sin detener la aplicación (`scripts/backup/sqlite_backup.py`). El origen se abre en solo lectura.

**El flujo `backup.yml`:** (1) en la VM, `backup_vm.sh` abre el volumen de datos en solo lectura y crea `framework_interno_<fecha>.sqlite.gz` + manifiesto + reporte; (2) trae la copia al runner; (3) **la restaura en una carpeta aislada y verifica** hash, `integrity_check`, filas por tabla y lectura de datos reales (la base de la VM no se toca); (4) sube la copia a Azure Blob (contenedor privado) si está configurado.

**Dónde se guardan (y qué NO se afirma todavía):**

| Lugar | Retención | Permiso necesario | Estado |
| --- | --- | --- | --- |
| VM: `/opt/framework/backups` | Las 14 más recientes (`KEEP_LOCAL`) | Usuario SSH con Docker | Preparado; **no ejecutado** |
| Azure Blob (cuenta y contenedor del `apply`) | `BACKUP_RETENTION_DAYS` (30 por defecto) por política de ciclo de vida + versionado/papelera de 7 días | **Storage Blob Data Contributor** de la identidad del flujo sobre el contenedor | Preparado; **no se subió ninguna copia** |
| GitHub | Solo los **reportes** (90 días): conteos, tamaño y hash, **sin datos** | — | Preparado |

La copia **no** se publica como artefacto de GitHub: contiene proyectos, perfiles de conexión (sin contraseñas), SQL e historial, y los artefactos pueden ser visibles para quien lea el repositorio.

El reporte (`reporte_copia.md`) incluye fecha, archivo, tamaño, SHA-256, resultado de `integrity_check`, claves foráneas y filas por tabla. El reporte de restauración (`reporte_restauracion.md`) lista cada comprobación.

**No cubierto:** la base Oracle de demostración (es desechable). La copia de la VM entera es otro mecanismo (copias de Azure).

**Restaurar en producción (manual, con la API detenida; no se ejecutó nunca):**
```bash
cd <VM_APP_DIR>
# 1. Verifique primero la copia en una carpeta aislada (genera restaurada.sqlite)
python3 <repo>/framework-pruebas-sql/scripts/backup/sqlite_restore_verify.py --backup <copia>.sqlite.gz --manifest <copia>.manifest.json --work-dir /tmp/restauracion
# 2. Pare solo la API
docker compose -f compose.yml --env-file .env.production stop api
# 3. Guarde la base actual y copie la restaurada (conserva el propietario del archivo)
docker run --rm -v framework_pruebas_sql_framework_data:/data -v /tmp/restauracion:/restore:ro python:3.12-slim \
  sh -c 'cp /data/framework_interno.db /data/framework_interno.db.antes-restauracion && cp /restore/restaurada.sqlite /data/framework_interno.db && chown --reference=/data/framework_interno.db.antes-restauracion /data/framework_interno.db'
# 4. Arranque y compruebe
docker compose -f compose.yml --env-file .env.production start api
docker inspect --format '{{.State.Health.Status}}' framework_api_prod
```

## 7. Release y despliegue

1. **Release** (`release.yml`, manual): indique `version` (`v1.0.0`). Valida el formato y que el tag no exista, corre las pruebas, construye la imagen, la publica en `ghcr.io/<propietario>/<repositorio>/framework-pruebas-sql:<versión>` y crea el release (con el reporte de pruebas). Si el paquete queda privado, cree `GHCR_USER` y `GHCR_TOKEN`.
2. **Despliegue** (`deploy.yml`, manual o con `deploy=true` en el release): requiere la **aprobación** en `azure-production`. En la VM, `deploy_remote.sh`: registra la imagen actual y le pone una etiqueta de reversión → hace la **copia consistente previa** (si falla, **no despliega**) → `docker pull` → recrea **solo** el servicio `api` (no toca Oracle, Caddy ni volúmenes) → **prueba de salud** (healthcheck del contenedor + `/health`) → si falla, **reversión automática** a la imagen anterior.
3. **Salud externa:** si definen `APP_PUBLIC_URL`, el flujo consulta `<URL>/health` desde Internet.
4. **Reversión manual:** `deploy.yml` con `action = rollback` (vacío = imagen anterior registrada, o indique `image_tag`).

**Límites que deben conocer:**
- Revertir la imagen **no revierte los datos**. Si la versión nueva aplicó migraciones de Alembic al arrancar, la base ya cambió: para volver al estado anterior hay que restaurar la copia previa (§6). No usen `alembic downgrade`.
- El `.env.production` vive solo en la VM; ningún flujo lo lee ni lo escribe.
- La capa `compose.release.yml` solo cambia la imagen de la API; la copian los flujos al directorio indicado en `VM_APP_DIR`.
- SSH desde GitHub usa IP variables: el puerto 22 de la VM debe aceptar conexiones de Internet (solo con llave). Alternativa más estricta: desplegar con `az vm run-command` (no se implementó).

## 8. Evidencias que deben guardar tras ejecutar

| Criterio | Evidencia |
| --- | --- |
| Terraform + reportes | Captura del flujo `plan` verde, `reporte_plan.md`, `cost_report.md`, `reporte_pruebas.md`; tras el `apply`, `terraform output` y el recurso en el portal |
| Objetos de BD | `reporte_alembic.md`, `reporte_liquibase.md` (idempotencia: 2.ª ejecución = 0), `reporte_pruebas_oracle.md` |
| Copias | `reporte_copia.md`, `reporte_restauracion.md`, captura del blob en el portal, resultado de la restauración |
| Release y despliegue | Release de GitHub, imagen en Packages, log de `deploy`, `last_deploy.json` de la VM, `/health` en el navegador |

## 9. Riesgos de costos y operación

- **Terraform por defecto:** una cuenta de almacenamiento LRS/Cool con unas pocas copias pequeñas cuesta céntimos al mes (el reporte lo estima con el supuesto de 5 GB); la VM existente **no cambia**. El presupuesto con alertas es opcional.
- **Modo «VM nueva»:** con los precios de lista del 19-oct-2026 consultados para la prueba, una `Standard_B2s` en `eastus2` + disco de 64 GB + IP estática suma del orden de **40 USD/mes** encendida las 24 h. **Es una estimación de lista, no su costo real** (créditos, impuestos y tráfico aparte). No se activa desde el workflow.
- **GitHub:** los minutos de Actions de repositorios privados y el almacenamiento de Packages tienen cuotas según el plan; el flujo `db-objects.yml` levanta Oracle en el runner (varios minutos por ejecución [estimación, sin medir]).
- **Operación:** el despliegue exige un puerto 22 abierto con llave; revisar `Required reviewers` evita que una sola persona despliegue; la copia no protege contra perder la VM entera (usar también las copias de Azure).

## 10. Verificaciones locales de esta fase y sus límites

- **Docker:** al probar Liquibase con un Oracle, un contenedor de prueba mío quedó bloqueado en estado *Created* y Docker Desktop dejó de arrancar contenedores nuevos (`docker run` se cuelga; `docker build` sí funciona). **No se reinició Docker Desktop** para no afectar los contenedores de ustedes (incluidos `framework_api_prod` y `framework_oracle_prod`, que no se tocaron). Quedan por borrar, cuando Docker responda: el contenedor `fw_oracle_lb_adopt` y la imagen `fw-phase3-buildcheck:local`.
- Por eso: Liquibase se validó con la distribución oficial 4.33.0 (extraída de la imagen local) ejecutada con Java del equipo, contra H2 en modo Oracle, y **no contra Oracle**; `backup_vm.sh` y `actionlint` no se ejecutaron.
- La prueba de **Liquibase real contra Oracle** la hará el flujo `db-objects.yml` en GitHub (o ustedes en local con Docker operativo).
