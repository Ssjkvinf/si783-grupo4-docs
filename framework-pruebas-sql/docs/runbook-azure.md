# Runbook de Azure — paso a paso

Guía para quien no domina Azure ni GitHub. Cada paso dice **dónde hacer clic o qué comando ejecutar**, **qué debe aparecer** (criterio de éxito), **qué captura tomar**, **cuánto cuesta** (siempre una **estimación** con precios de lista; no es gasto real) y **qué hacer si falla**.

Reglas de oro:

- **La VM que ya funciona no se reemplaza.** Terraform solo la lee; el despliegue solo recrea el contenedor `api`.
- **Ningún secreto se pega en chats, correos, issues ni archivos del repositorio.** Va directo a *GitHub → Secrets* o se queda en la VM.
- Si un paso dice **DETÉNGASE**, no siga hasta entender el problema.
- Anote en cada paso el estado: *creado · probado local · ejecutado en GitHub · ejecutado en Azure*.

Marcadores que debe reemplazar: `<SUSCRIPCION>` (ID de la suscripción), `<GRUPO>` (grupo de recursos de la VM), `<VM>` (nombre de la VM), `<HOST>` (IP o DNS de la VM), `<USUARIO_VM>` (usuario SSH), `<CARPETA_APP>` (carpeta de la VM con `compose.yml` y `.env.production`), `<CUENTA_COPIAS>` (nombre nuevo para la cuenta de copias, 3‑24 minúsculas y números), `<APP_ID>` (identificador del service principal).

Capturas: guárdelas en una carpeta `evidencias/azure/` **fuera** del repositorio (pueden mostrar IP o nombres) y súbalas solo a los informes. Antes de cada captura, oculte IP, correos e identificadores de suscripción.

---

## A. Fusionar el PR #6 en `main` y activar Pages

1. Antes de fusionar, suba los commits locales pendientes (ver el plan de commits del informe de la fase) y espere a que los checks del PR terminen en verde.
2. **GitHub → Pull requests → #6 → pestaña *Checks***: todos con ✔.
3. Botón verde **Merge pull request** → en la flecha de al lado elija **Create a merge commit** (no *Squash* ni *Rebase*: así se conserva la autoría de cada commit) → **Confirm merge**.
4. **Settings → Pages → Build and deployment → Source: GitHub Actions**.

| Criterio de éxito | Captura | Costo (estimación) | Si falla |
| --- | --- | --- | --- |
| El PR dice *Merged*; en `main` aparece un commit «Merge pull request #6». En Pages, *Source* = GitHub Actions. | `A1-pr6-merged.png`, `A2-pages-source.png` | 0 | Si *Merge* está gris: faltan checks o aprobaciones; abra el check en rojo y lea el error. Si Pages no muestra la opción: la organización puede bloquearlo; pídalo al docente. |

## B. Preparar GitHub y la identidad de Azure

### B1. Entornos (una vez)

**Settings → Environments → New environment**, uno por fila:

| Entorno | Revisores obligatorios | Para qué |
| --- | --- | --- |
| `azure-plan` | No | Plan de Terraform (solo lectura de Azure) |
| `azure-backup` | No (opcional: Gerald) | Copia de la SQLite |
| `azure-apply` | **Sí: Gerald** (marque *Prevent self-review*) | Aplicar el plan revisado |
| `azure-production` | **Sí: Gerald** (marque *Prevent self-review*) | Desplegar y revertir |

Aviso: en repositorios **privados**, los revisores obligatorios exigen un plan de pago de GitHub (Pro/Team/Enterprise); en repositorios públicos son gratis. Si no aparece *Required reviewers*, los flujos igual exigen ejecución manual y, para `apply`, escribir `APPLY`; anótelo como limitación.

| Criterio de éxito | Captura | Costo | Si falla |
| --- | --- | --- | --- |
| Los 4 entornos aparecen en la lista; `azure-apply` y `azure-production` muestran «1 reviewer». | `B1-entornos.png` | 0 | Sin permiso de administrador del repositorio no se ven *Settings*: pídalo al docente. |

### B2. Datos de la VM y service principal (los ejecuta Kevin en su terminal con `az`)

Instale la CLI de Azure si no la tiene (`winget install Microsoft.AzureCLI`) y ejecute, **uno por uno**:

```bash
az login
az account show --query "{suscripcion:id, tenant:tenantId}" -o table
az vm list -d -o table --query "[].{nombre:name, grupo:resourceGroup, tamano:hardwareProfile.vmSize, region:location, ip:publicIps}"
```

Anote `<SUSCRIPCION>`, el tenant, `<GRUPO>`, `<VM>`, tamaño, región e IP. **No los pegue en el repositorio.**

Service principal con el **permiso mínimo** (lee la VM y crea el almacenamiento de copias; Azure le impide modificar la VM):

```bash
az ad sp create-for-rbac --name "sp-framework-sql" --role Reader --scopes /subscriptions/<SUSCRIPCION>/resourceGroups/<GRUPO>
```

La salida trae `appId` (→ `ARM_CLIENT_ID` y `<APP_ID>`), `password` (→ `ARM_CLIENT_SECRET`; **cópielo directo a GitHub y cierre la terminal**) y `tenant` (→ `ARM_TENANT_ID`).

```bash
az role assignment create --assignee <APP_ID> --role "Storage Account Contributor" --scope /subscriptions/<SUSCRIPCION>/resourceGroups/<GRUPO>
```

Opcionales:

```bash
# Gasto REAL en el reporte de costos (COST_REAL_ENABLED=true)
az role assignment create --assignee <APP_ID> --role "Cost Management Reader" --scope /subscriptions/<SUSCRIPCION>/resourceGroups/<GRUPO>
# Presupuesto con alertas (BUDGET_AMOUNT y BUDGET_ALERT_EMAILS)
az role assignment create --assignee <APP_ID> --role "Cost Management Contributor" --scope /subscriptions/<SUSCRIPCION>/resourceGroups/<GRUPO>
```

Estado remoto de Terraform (solo si no existe uno): una cuenta y un contenedor pequeños en el mismo grupo.

```bash
az storage account create -n <CUENTA_ESTADO> -g <GRUPO> --sku Standard_LRS --min-tls-version TLS1_2 --allow-blob-public-access false
az storage container create -n tfstate --account-name <CUENTA_ESTADO> --auth-mode login
```

| Criterio de éxito | Captura | Costo (estimación) | Si falla |
| --- | --- | --- | --- |
| `az role assignment list --assignee <APP_ID> -o table` muestra *Reader* y *Storage Account Contributor* sobre `<GRUPO>` (y ningún *Contributor* ni *Owner*). | `B2-roles-sp.png` (sin el secreto) | Service principal: 0. Cuenta de estado: centavos de dólar al mes (archivo de pocos KB). | «Insufficient privileges» al crear el service principal: las cuentas estudiantiles a veces no pueden; pida al docente que lo cree con estos mismos roles. **Nunca** use *Owner* o *Contributor* para salir del paso. |

### B3. Llave SSH de despliegue y carpetas en la VM

```bash
ssh-keygen -t ed25519 -f deploy_key -C "github-actions-framework" -N ""
ssh-keyscan -t ed25519 <HOST>
```

- Añada el contenido de `deploy_key.pub` a `~/.ssh/authorized_keys` de `<USUARIO_VM>` en la VM.
- Copie el **contenido** de `deploy_key` (privada) al secreto `VM_SSH_KEY` y **borre** `deploy_key` y `deploy_key.pub` de su PC.
- La salida de `ssh-keyscan` va al secreto `VM_SSH_KNOWN_HOSTS` (compare la huella con la que ya conoce de la VM).
- En la VM: `sudo mkdir -p /opt/framework/backups /opt/framework/releases && sudo chown -R "$USER" /opt/framework`.

### B4. Secretos y variables

Secretos (*Settings → Environments → [entorno] → Environment secrets*):

| Secreto | Entornos | Contenido |
| --- | --- | --- |
| `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID` | `azure-plan`, `azure-apply`, `azure-backup` | Del service principal (B2) |
| `VM_HOST`, `VM_USER` | `azure-backup`, `azure-production` | IP/DNS y usuario SSH de la VM |
| `VM_SSH_KEY`, `VM_SSH_KNOWN_HOSTS` | `azure-backup`, `azure-production` | Llave privada de despliegue y huella del servidor (B3) |
| `GHCR_USER`, `GHCR_TOKEN` | `azure-production` | Solo si el paquete de GHCR queda privado: usuario y token con `read:packages` |

`GITHUB_TOKEN` lo crea GitHub solo; no se configura.

Variables (*Settings → Secrets and variables → Actions → Variables*, a nivel de repositorio):

| Variable | Obligatoria para | Valor |
| --- | --- | --- |
| `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME` | Plan | `<GRUPO>`, `<VM>` |
| `AZURE_VM_SIZE`, `AZURE_LOCATION` | Estimación de la VM (opcional) | Tamaño y región de B2 |
| `BACKUP_STORAGE_ACCOUNT` | Plan y copia | `<CUENTA_COPIAS>` (nueva; Terraform la crea) |
| `BACKUP_RETENTION_DAYS`, `BACKUP_CONTAINER` | Opcional | `30`, `sqlite-backups` |
| `TFSTATE_RESOURCE_GROUP`, `TFSTATE_STORAGE_ACCOUNT`, `TFSTATE_CONTAINER` | Plan y apply | `<GRUPO>`, `<CUENTA_ESTADO>`, `tfstate` |
| `BUDGET_AMOUNT`, `BUDGET_ALERT_EMAILS` | Opcional (presupuesto) | p. ej. `20` y `["correo@dominio"]` (con corchetes y comillas) |
| `COST_REAL_ENABLED` | Opcional | `true` para el gasto real |
| `VM_APP_DIR` | Despliegue | `<CARPETA_APP>` |
| `VM_BACKUP_DIR`, `APP_DATA_VOLUME` | Opcional | `/opt/framework/backups`, el volumen que muestra el preflight |
| `APP_PUBLIC_URL` | Opcional | URL pública sin barra final (prueba de salud externa) |
| `BACKUP_SCHEDULE_ENABLED` | Opcional | `true` para la copia diaria |

| Criterio de éxito | Captura | Costo | Si falla |
| --- | --- | --- | --- |
| Cada entorno lista sus secretos (GitHub nunca muestra el valor) y la pestaña *Variables* tiene las obligatorias. | `B4-secretos-por-nombre.png`, `B4-variables.png` | 0 | Si un flujo dice «Faltan secretos» o «Faltan variables», el mensaje nombra cuál; revise que esté en el **entorno** correcto. |

## C. Ejecutar en GitHub lo que no toca Azure

**Actions →** (menú izquierdo) → flujo → **Run workflow** → rama `main`:

| Flujo | Entrada | Criterio de éxito | Captura |
| --- | --- | --- | --- |
| *Documentación técnica (Pages)* (`pages.yml`) | — | Verde; el resumen muestra la URL de la documentación y abre en el navegador | `C1-pages-url.png` |
| *Tests* (`tests.yml`) | Se ejecuta con el push a `main` | Verde; artefacto con el reporte de pruebas | `C2-tests.png` |
| *Objetos de base de datos (Alembic + Liquibase)* (`db-objects.yml`, con pruebas Oracle de CI) | — | Verde; resumen con «Reporte de Liquibase» y las pruebas Oracle superadas | `C3-liquibase.png` |
| *Infraestructura (Terraform)* | `action = validate` | Verde; tabla con `fmt`, `validate` y **`terraform test` (plan simulado: no toca la VM)** en *success* | `C4-terraform-validate.png` |

Costo (estimación): 0 en repositorios públicos; en privados consume minutos del plan gratuito (≈ 15‑30 min por ronda). Si falla: abra el paso en rojo, copie el error (sin secretos) y corríjalo antes de seguir.

## D. Revisión previa en la VM (solo lectura)

Desde su PC, en la carpeta del repositorio:

```bash
scp framework-pruebas-sql/scripts/deploy/preflight_vm.sh <USUARIO_VM>@<HOST>:/tmp/preflight_vm.sh
ssh <USUARIO_VM>@<HOST> "bash /tmp/preflight_vm.sh"
```

(Si la API no se llama `framework_api_prod`: `ssh … "API_CONTAINER=<nombre> APP_DIR=<CARPETA_APP> bash /tmp/preflight_vm.sh"`.)

El script **no cambia nada** y nunca muestra valores secretos. Revise el bloque **Resumen**:

| Si dice | Haga |
| --- | --- |
| `APP_SESSION_SECRET` o `APP_ACCESS_PASSWORD` usa un valor de ejemplo: SÍ | Edite `<CARPETA_APP>/.env.production` en la VM (`nano`) con valores propios. **DETÉNGASE** hasta corregirlo: la versión nueva respondería 503. |
| Recomendado `APP_REGISTRATION_ENABLED=false` | Añádalo o cámbielo en `.env.production`. |
| Sin `FORWARDED_ALLOW_IPS` | Haga una copia del compose actual (`cp compose.yml compose.yml.bak-$(date +%F)`), compárelo con el del repositorio (`diff`) y reemplácelo **solo si** el `name:` del proyecto y el volumen de `/data` son los mismos que muestra el preflight. Si difieren, **DETÉNGASE** y consulte: otro nombre de volumen dejaría la app con una base vacía. |
| No hay copias recientes | Haga el paso G antes del despliegue (H también hace una copia previa). |
| La versión nueva aplicará migraciones | Normal: el despliegue hace una copia antes. Ver el aviso del paso I. |

| Criterio de éxito | Captura | Costo | Si falla |
| --- | --- | --- | --- |
| El resumen dice «Todo en orden» o solo avisos que usted ya resolvió. | `D1-preflight.png` (oculte la IP) | 0 | «Permission denied» con Docker: use un usuario del grupo `docker` o `sudo bash /tmp/preflight_vm.sh`. |

## E. Plan real de Terraform (lee Azure, no cambia nada)

**Actions → Infraestructura (Terraform) → Run workflow → `action = plan`.**

Qué debe decir el resumen del job *Plan de Terraform y reportes*:

- **Creaciones: 3** (cuenta de copias, contenedor, política de retención; **4** si configuró el presupuesto).
- **Modificaciones: 0 · Eliminaciones: 0 · Reemplazos: 0.**
- La VM y su grupo de recursos solo aparecen como lecturas (*data*).

**DETÉNGASE** si ve «Plan BLOQUEADO», cualquier modificación, eliminación o reemplazo, o un recurso de red, disco o VM. No apruebe nada; revise las variables.

Descargue los artefactos `reportes-terraform` (reporte del plan, `costos/cost_report.md`, reporte de pruebas) y `reporte-pruebas-infra`.

| Criterio de éxito | Captura | Costo (estimación) | Si falla |
| --- | --- | --- | --- |
| Job verde, «Plan sin eliminaciones ni reemplazos: correcto», reporte de costos marcado **ESTIMACIÓN** y, con `COST_REAL_ENABLED=true`, una sección de gasto real (o «No disponible»). | `E1-plan-resumen.png`, `E2-costos-estimado.png`, `E3-pruebas-superadas.png` | El plan es gratis. El reporte estima la cuenta de copias en centavos al mes (pocos MB, LRS, nivel Cool) y muestra la VM aparte, solo como referencia. | «AuthorizationFailed»: falta un rol de B2. «Backend…not found»: revise `TFSTATE_*`. «StorageAccountAlreadyTaken»: elija otro `BACKUP_STORAGE_ACCOUNT`. |

## F. Aplicar el plan (solo si E salió limpio)

**Actions → Infraestructura (Terraform) → Run workflow → `action = apply`, `confirm_apply = APPLY`.**

1. El flujo vuelve a planificar; el job *Aplicar el plan revisado* queda **esperando aprobación**.
2. Gerald abre el run, lee el resumen del plan (debe ser igual que en E) y pulsa **Review deployments → Approve**.
3. Después, asigne el permiso para subir copias (Kevin, con `az`):

```bash
az role assignment create --assignee <APP_ID> --role "Storage Blob Data Contributor" \
  --scope /subscriptions/<SUSCRIPCION>/resourceGroups/<GRUPO>/providers/Microsoft.Storage/storageAccounts/<CUENTA_COPIAS>/blobServices/default/containers/sqlite-backups
```

| Criterio de éxito | Captura | Costo (estimación) | Si falla |
| --- | --- | --- | --- |
| Job verde; «Terraform apply completado» con `almacenamiento_de_copias`. En el portal, la cuenta aparece en `<GRUPO>` con el contenedor `sqlite-backups` **privado**. La VM sigue *Running* sin cambios. | `F1-aprobacion.png`, `F2-apply-ok.png`, `F3-portal-cuenta.png` | La cuenta de copias: centavos de dólar al mes con el volumen esperado (unos MB). | «Saved plan is stale»: el estado cambió; repita E y F. Nunca use `destroy`: el flujo no lo tiene a propósito. |

## G. Copia de la SQLite y restauración verificada

**Actions → Copia de seguridad de la SQLite → Run workflow** (`upload_to_blob = true`).

El flujo: copia consistente en la VM (no detiene la app) → trae la copia al runner → comprueba el hash → la **restaura en una carpeta aislada** y verifica integridad y conteos → la sube al contenedor privado.

| Criterio de éxito | Captura | Costo (estimación) | Si falla |
| --- | --- | --- | --- |
| Verde; el resumen muestra el reporte de restauración (integridad `ok`, filas por tabla) y «Subida a … (contenedor privado)». En el portal, el archivo `framework_interno_<fecha>.sqlite.gz` aparece en `sqlite-backups`. | `G1-copia-resumen.png`, `G2-restauracion.png`, `G3-blob.png` | Unos KB/MB en Blob: menos de un centavo al mes. | «no existe el volumen»: defina `APP_DATA_VOLUME` con el que mostró el preflight. «AuthorizationPermissionMismatch»: falta el rol del paso F. La copia nunca se publica como artefacto (contiene datos). |

Restaurar de verdad (solo si hiciera falta) sigue `docs/operacion-fase3.md` §6 con la API detenida; no es parte de esta demostración.

## H. Release v1.0.0 y despliegue

**Actions → Release (imagen versionada) → Run workflow → `version = v1.0.0`, `deploy = true`.**

1. Corre las pruebas, construye la imagen y la publica en GHCR, crea el release `v1.0.0` con el reporte de pruebas.
2. El job de despliegue espera la aprobación de Gerald en `azure-production` → **Approve**.
3. En la VM: copia previa → descarga de la imagen → recrea **solo** `api` → prueba de salud → si falla, reversión automática (también si `compose up` falla a medias) y reporte en `/opt/framework/releases/last_deploy.json`.

Si el paquete de GHCR quedó **privado**, antes de aprobar haga una de dos: márquelo público (*GitHub → su perfil u organización → Packages → el paquete que termina en `framework-pruebas-sql` → Package settings → Change visibility*), o configure `GHCR_USER`/`GHCR_TOKEN`.

Comprobación del flujo de usuario (en el navegador, URL pública):

1. `https://<dominio>/health` → `{"status":"ok", …}`.
2. Ingrese con el administrador de `.env.production` (se crea en el primer ingreso) y cambie su contraseña.
3. **Usuarios y permisos → Nuevo usuario**: cuentas de Gerald y del docente (ver `docs/seguridad.md` § «Cuentas en producción»).
4. Ejecute una suite (o la **Demostración guiada** con la conexión TEST de la VM).
5. **Historial**: la ejecución aparece con «Quién» = su usuario.
6. **Uso del producto**: cifras con datos reales; las ejecuciones antiguas figuran como «sin usuario».

| Criterio de éxito | Captura | Costo (estimación) | Si falla |
| --- | --- | --- | --- |
| Release `v1.0.0` visible en *Releases*; imagen en *Packages*; job de despliegue verde; `/health` responde; ingreso, suite, historial y panel funcionan. | `H1-release.png`, `H2-paquete.png`, `H3-deploy.png`, `H4-health.png`, `H5-login.png`, `H6-suite.png`, `H7-historial.png`, `H8-uso-real.png` | GHCR: gratis para paquetes públicos; la VM sigue con su costo habitual. | Lea `last_deploy.json` en la VM: `resultado` y `reversion_aplicada`. Si dice `intentada_sin_exito`, la base pudo migrar: detenga la API, restaure la copia previa (`docs/operacion-fase3.md` §6) y arranque la imagen anterior. |

## I. Rollback de prueba

**Importante: revertir la imagen NO revierte los datos.** La versión nueva migra la base al arrancar (tabla de usuarios, columna «ejecutado por»). Una imagen **anterior** a esa migración **no arranca** con la base ya migrada: al iniciar ejecuta `alembic upgrade head`, que falla con «Can't locate revision identified by 'a4b8c2d9e1f0'» (comprobado en local con el código del commit `9d11c07`), y el contenedor se detiene. Por eso la prueba de rollback se hace **entre dos versiones nuevas**:

1. Publique `v1.0.1` (*Release → `version = v1.0.1`, `deploy = true`*), por ejemplo con un cambio solo de documentación.
2. **Actions → Despliegue → Run workflow → `action = rollback`, `image_tag = v1.0.0`** → aprobación de Gerald.
3. Compruebe `/health` y que la app sigue funcionando con los mismos datos.

| Criterio de éxito | Captura | Costo | Si falla |
| --- | --- | --- | --- |
| Job verde; en la VM, `/opt/framework/releases/rollback_<fecha>.json` con `"estado": "healthy"` y la imagen `v1.0.0`; los datos (usuarios, historial) siguen ahí. | `I1-rollback.png`, `I2-health-tras-rollback.png` | 0 | Si de verdad necesita volver a la versión **anterior a los usuarios**: detenga la API, restaure la copia previa al despliegue (§6 del manual) y luego despliegue la imagen anterior. Es un procedimiento manual, con pérdida de lo ocurrido desde la copia. |

---

## Resumen de costos (estimación, precios de lista en USD, sin impuestos ni créditos)

| Elemento | Costo mensual aproximado | Nota |
| --- | --- | --- |
| VM existente | El de siempre según su tamaño | No lo cambia este runbook; el reporte de costos lo muestra aparte si define `AZURE_VM_SIZE` y `AZURE_LOCATION` |
| Cuenta de copias (LRS, Cool) y cuenta de estado | Centavos | Pocos MB; las transacciones de una copia diaria son despreciables |
| Presupuesto | 0 | Solo envía alertas; no limita el gasto |
| GitHub Actions, Pages, GHCR | 0 en repositorios públicos | En privados se consumen minutos y almacenamiento del plan gratuito |

El gasto **real** solo se conoce en *Azure Portal → Cost Management* o con `COST_REAL_ENABLED=true`. Nada de esta tabla se midió.
