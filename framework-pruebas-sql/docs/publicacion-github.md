# Publicación en GitHub: autoría, primer push, configuración y primeras ejecuciones

Guía para Kevin y Gerald. **Es un plan: nada de esto se ejecutó.** Todo lo de GitHub y Azure sigue sin comprobarse hasta que se haga y se guarde evidencia. Los nombres de secretos y variables están en `docs/operacion-fase3.md` §3 (nunca escriba sus valores en el repositorio, en issues ni en capturas).

## 1. Que las contribuciones cuenten (autoría)

GitHub atribuye un commit a una cuenta por el **correo del commit**, que debe estar **verificado en esa cuenta**.

| Comprobación | Cómo |
| --- | --- |
| Qué autor usará Git | `git config user.name` y `git config user.email` (para ver de qué archivo vienen: `git config --show-origin --get-all user.email`). En el equipo de Kevin están configurados `Kevin` y `kh2023078335@virtual.upt.pe`, el mismo correo de los 35 commits anteriores |
| Que el correo está en la cuenta | GitHub → *Settings → Emails*: el correo debe figurar como **Verified**. Si no quiere publicarlo, use el correo `ID+usuario@users.noreply.github.com` que GitHub muestra ahí: `git config user.email "ID+usuario@users.noreply.github.com"` (solo en este repositorio, sin `--global`) |
| Que quedó atribuido | Tras el push, abra un commit en GitHub: debe mostrar el avatar y el nombre de la cuenta con enlace al perfil; si sale gris o sin enlace, el correo no está asociado. Luego *Insights → Contributors* del repositorio |
| Gerald, en su equipo | Los mismos tres comandos **con su cuenta**; `git config user.name "Gerald …"` y su correo verificado. No usar la configuración de Kevin ni commits «en nombre de» el otro. Tras su primer commit: `git log -1 --format='%an <%ae>'` y `git shortlog -sne` |

Notas: los commits hechos desde la web de GitHub salen con *committer* «GitHub»; el *author* sigue siendo quien los escribió. Las contribuciones al gráfico del perfil cuentan en la rama por defecto.

## 2. Antes del primer push (Kevin)

1. `python -m pytest -q` → esperado hoy: 330 superadas, 23 omitidas, 0 fallidas.
2. `python scripts/docs/gen_docs.py --check` → «OK» (si no, ejecutar sin `--check`).
3. `python -m mkdocs build --strict -d site` → sin avisos; `site/` no se sube.
4. Ejecutar los commits con el script del plan (`publicar_kevin.ps1`): regenera la documentación, muestra `git diff --cached` y pide confirmación antes de cada uno.
5. **Recomendado:** crear antes una rama (`git switch -c feature/entrega-unidad-ii`) y publicar con un *pull request*: los flujos de `pull_request` corren antes de tocar `main`, y Gerald puede revisarlo (revisión cruzada que también cuenta como participación).

### Si `origin/main` avanzó
`git fetch origin` y `git log --oneline HEAD..origin/main`. Si hay commits nuevos (por ejemplo, de Gerald): `git rebase origin/main` (sus commits aún no están publicados, así que el rebase es seguro). Si hay conflictos: `git status`, resolver, `git add <archivo>`, `git rebase --continue`; después repetir `gen_docs.py` y `pytest`. No usar `push --force` sobre `main`. Si solo se tocaron archivos distintos, no habrá conflicto.

## 3. Qué configurar en GitHub (Kevin; sin pegar valores aquí)

| Pantalla | Qué hacer | Qué comprobar y qué captura tomar |
| --- | --- | --- |
| *Settings → Pages* | *Build and deployment → Source*: **GitHub Actions** | Aparece «GitHub Actions» seleccionado. Captura `gh_01_pages_source.png` |
| *Settings → Actions → General* | Permitir las acciones que usan los flujos (`actions/*`, `hashicorp/setup-terraform`, `terraform-linters/setup-tflint`, `docker/*`): «Allow all actions» o «Allow … and select non-… » incluyendo esas. *Workflow permissions*: **Read repository contents and packages** (los flujos piden sus propios permisos) | Captura `gh_02_actions_general.png`. Si la organización lo bloquea, preguntar al docente |
| *Settings → Environments* | Crear `azure-plan` (sin revisores), `azure-backup` (sin revisores), `azure-apply` y `azure-production` (**Required reviewers** = la otra persona; activar *Prevent self-review*). `github-pages` se crea sola | Captura `gh_03_environments.png` (sin valores de secretos) |
| *Environments → secrets / Variables* | Solo los **nombres** de `docs/operacion-fase3.md` §3: secretos `ARM_*` (azure-plan, azure-apply, azure-backup), `VM_HOST`, `VM_USER`, `VM_SSH_KEY`, `VM_SSH_KNOWN_HOSTS` (azure-backup, azure-production), `GHCR_USER`, `GHCR_TOKEN` (azure-production); variables del repositorio `AZURE_*`, `BACKUP_*`, `TFSTATE_*`, `VM_APP_DIR`, `VM_BACKUP_DIR`, `APP_DATA_VOLUME`, `APP_PUBLIC_URL`, `COST_REAL_ENABLED`. **No son necesarios para los primeros flujos** (tests, sql-checks, db-objects, docs-generate, pages, infra validate): se configuran solo cuando se ejecute plan, copia o despliegue | Captura de la lista de **nombres** `gh_04_secretos_nombres.png` (nunca los valores) |
| *Settings → Branches* (si hay permiso) | Regla para `main`: exigir pull request y que pasen `Tests` y `Documentación (generar)`. Aviso: con esta regla nadie hace push directo | Captura `gh_05_proteccion_main.png`. Es opcional y puede no estar permitida |
| *Settings → General → Features / Packages* | Los Packages los usa `release.yml` (no se ejecuta ahora) | Solo comprobar que existen en la organización |
| *Actions* (pestaña) | Habilitar los flujos tras el primer push (GitHub puede pedir confirmación en repositorios de organización) | `gh_06_actions_habilitadas.png` |

## 4. Primeras ejecuciones y criterio de éxito

Ninguna incluye `apply`, `release` ni despliegue. Guarde la captura del resumen del job y del artefacto de cada una.

| Orden | Flujo | Cómo | Éxito | Si falla |
| --- | --- | --- | --- | --- |
| 1 | `Tests` | Se dispara con el PR | Verde; artefacto `reporte-pruebas` con el reporte; 330 superadas y 23 omitidas (puede diferir si hubo cambios) | Leer el primer fallo; lo más probable es Python 3.12 (no probado en local) o una ruta |
| 2 | `Documentación (generar)` | Se dispara con el PR (o *Run workflow*) | Verde; resumen «Ninguna: lo versionado coincide con lo generado»; artefacto `documentacion-generada` | Si falla por desfase: descargar el artefacto o ejecutar `gen_docs.py` y subir lo regenerado |
| 3 | `Objetos de base de datos (Alembic + Liquibase)` | PR/push o *Run workflow* | Verde; Alembic sin diferencias; Liquibase aplica 4 changesets y la 2.ª ejecución 0; reporte como artefacto. **Es la primera vez que corre contra un Oracle real** (gvenzl en el ejecutor) | Revisar el log de Liquibase y los permisos del esquema (`grant_migration_privileges.sql`); si falla la descarga de la imagen, reintentar |
| 4 | `Comprobaciones SQL (CLI + Excel)` | *Run workflow* normal y luego con `provocar_dato_invalido = true` | La normal: código 0, resumen con 5 PASS, artefacto `reporte-sql-checks`. La provocada: **falla** con código 1 y el informe muestra el FAIL (eso es el éxito de la demostración) | Si la normal falla, revisar el paso del Oracle del ejecutor |
| 5 | `Documentación técnica (Pages)` | Con el PR solo construye; tras fusionar en `main` (o *Run workflow* en `main`) publica | La construcción verde en el PR; tras `main`, `publicar` verde y una URL de `github.io`. Verificar que los diagramas Mermaid se dibujan (necesitan internet) | Si `publicar` falla por entorno: revisar *Pages → Source* y el entorno `github-pages` |
| 6 | `Infraestructura (Terraform)` | Se dispara con el PR: `validate` y `tests` (sin credenciales). `plan` solo si ya configuraron los secretos `ARM_*` y variables, con *Run workflow* → `plan` | `validate` y `tests` verdes. `plan` genera `reporte_plan.md` y el reporte de costos **estimado** (precios de lista) | `plan` falla con un mensaje claro si faltan secretos o variables (no se fabrica un plan) |

No ejecutar todavía: `apply`, `Release`, `Despliegue`, `Copia de seguridad`.
