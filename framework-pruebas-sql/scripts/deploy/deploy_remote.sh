#!/usr/bin/env bash
# Despliega una imagen versionada de la API en la VM (SE EJECUTA EN LA VM; lo invoca deploy.yml por SSH).
#
# Qué hace, en orden:
#   1. Comprueba requisitos y registra la imagen que está corriendo (para poder volver atrás).
#   2. Copia de seguridad CONSISTENTE de la SQLite (si falla, no se despliega) — salvo SKIP_BACKUP=1.
#   3. Descarga la imagen nueva (docker pull) y la etiqueta como candidata.
#   4. Recrea SOLO el servicio `api` con esa imagen (no toca Oracle ni Caddy ni los volúmenes).
#   5. Prueba de salud: el healthcheck del contenedor debe quedar «healthy» y /health debe responder.
#   6. Si la salud falla: REVERSIÓN automática a la imagen anterior y salida con error.
#
# Variables obligatorias:
#   APP_DIR     carpeta de la VM con compose.yml y .env.production (la de infra/production del repositorio)
#   API_IMAGE   imagen completa, p. ej. ghcr.io/<propietario>/<repo>/framework-pruebas-sql:v1.0.0
# Opcionales:
#   GHCR_USER / GHCR_TOKEN   solo si el paquete es privado (el token se lee por variable de entorno, nunca por argumento)
#   API_CONTAINER (framework_api_prod) · HEALTH_TIMEOUT (120 s) · SKIP_BACKUP (0) · REPORT_DIR (/opt/framework/releases)
#
# IMPORTANTE: revertir la imagen NO revierte la base. Si la versión nueva aplicó migraciones de Alembic al arrancar,
# la base ya cambió; para volver al estado anterior de los datos hay que restaurar la copia previa (docs/operacion-fase3.md).
set -euo pipefail

: "${APP_DIR:?Falta APP_DIR}" "${API_IMAGE:?Falta API_IMAGE}"
API_CONTAINER="${API_CONTAINER:-framework_api_prod}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
SKIP_BACKUP="${SKIP_BACKUP:-0}"
REPORT_DIR="${REPORT_DIR:-/opt/framework/releases}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

compose() {
    docker compose -f "$APP_DIR/compose.yml" -f "$APP_DIR/compose.release.yml" --env-file "$APP_DIR/.env.production" "$@"
}

wait_healthy() {
    local deadline=$((SECONDS + HEALTH_TIMEOUT)) status=""
    while [ "$SECONDS" -lt "$deadline" ]; do
        status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}sin-healthcheck{{end}}' "$API_CONTAINER" 2>/dev/null || echo ausente)"
        if [ "$status" = "healthy" ]; then
            # Comprobación explícita del endpoint /health desde dentro del contenedor
            if docker exec "$API_CONTAINER" python -c "import json,urllib.request;d=json.load(urllib.request.urlopen('http://localhost:8000/health',timeout=5));print('health:',d.get('status'),'version:',d.get('version'));raise SystemExit(0 if d.get('status')=='ok' else 1)"; then
                return 0
            fi
        fi
        sleep 3
    done
    log "El contenedor no quedó saludable en ${HEALTH_TIMEOUT}s (último estado: ${status})"
    docker logs --tail 40 "$API_CONTAINER" 2>&1 | sed 's/^/    | /' || true
    return 1
}

# ---- 1. Requisitos y estado actual
command -v docker >/dev/null || fail "docker no está instalado"
docker compose version >/dev/null 2>&1 || fail "falta el plugin docker compose"
[ -f "$APP_DIR/compose.yml" ] || fail "no existe $APP_DIR/compose.yml"
[ -f "$APP_DIR/.env.production" ] || fail "no existe $APP_DIR/.env.production (se crea a mano en la VM; nunca viaja por GitHub)"
[ -f "$APP_DIR/compose.release.yml" ] || fail "falta $APP_DIR/compose.release.yml (lo copia el workflow)"
mkdir -p "$REPORT_DIR"

PREVIOUS_ID="$(docker inspect --format '{{.Image}}' "$API_CONTAINER" 2>/dev/null || true)"
PREVIOUS_REF="$(docker inspect --format '{{.Config.Image}}' "$API_CONTAINER" 2>/dev/null || true)"
ROLLBACK_TAG=""
if [ -n "$PREVIOUS_ID" ]; then
    ROLLBACK_TAG="framework-rollback:${STAMP}"
    docker tag "$PREVIOUS_ID" "$ROLLBACK_TAG"          # etiqueta estable para poder volver atrás
    printf '%s\n' "$ROLLBACK_TAG" > "$REPORT_DIR/previous_image.txt"
    log "Imagen actual: ${PREVIOUS_REF} (${PREVIOUS_ID:0:19}…) → etiqueta de reversión ${ROLLBACK_TAG}"
else
    log "No hay un contenedor ${API_CONTAINER} en marcha: primer despliegue, no habrá reversión automática."
fi

# ---- 2. Copia de seguridad consistente previa
if [ "$SKIP_BACKUP" = "1" ]; then
    log "ADVERTENCIA: SKIP_BACKUP=1, no se hace copia previa."
else
    log "Copia de seguridad consistente previa al despliegue"
    BACKUP_DIR="${BACKUP_DIR:-/opt/framework/backups}" bash "$HERE/backup_vm.sh" >"$REPORT_DIR/pre_deploy_backup_${STAMP}.log" 2>&1 \
        || { cat "$REPORT_DIR/pre_deploy_backup_${STAMP}.log"; fail "la copia previa falló: no se despliega"; }
    log "Copia previa correcta"
fi

# ---- 3. Descargar la imagen
if [ -n "${GHCR_TOKEN:-}" ] && [ -n "${GHCR_USER:-}" ]; then
    printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
fi
log "Descargando ${API_IMAGE}"
docker pull "$API_IMAGE" >/dev/null

# ---- 4. Recrear solo la API
export API_IMAGE
log "Recreando el servicio api con ${API_IMAGE}"
compose up -d --no-build --no-deps api

# ---- 5. Prueba de salud
RESULT="ok"; ROLLED_BACK="no"
if ! wait_healthy; then
    RESULT="fallo_de_salud"
    # ---- 6. Reversión automática
    if [ -n "$ROLLBACK_TAG" ]; then
        log "REVERSIÓN automática a ${ROLLBACK_TAG}"
        API_IMAGE="$ROLLBACK_TAG" compose up -d --no-build --no-deps api
        if wait_healthy; then ROLLED_BACK="si"; else ROLLED_BACK="intentada_sin_exito"; fi
    else
        ROLLED_BACK="imposible_sin_imagen_previa"
    fi
fi

cat > "$REPORT_DIR/deploy_${STAMP}.json" <<EOF
{
  "fecha_utc": "${STAMP}",
  "imagen_nueva": "${API_IMAGE}",
  "imagen_anterior": "${PREVIOUS_REF}",
  "etiqueta_de_reversion": "${ROLLBACK_TAG}",
  "resultado": "${RESULT}",
  "reversion_aplicada": "${ROLLED_BACK}",
  "copia_previa": "$([ "$SKIP_BACKUP" = "1" ] && echo omitida || echo realizada)"
}
EOF
cp "$REPORT_DIR/deploy_${STAMP}.json" "$REPORT_DIR/last_deploy.json"
cat "$REPORT_DIR/deploy_${STAMP}.json"

if [ "$RESULT" = "ok" ]; then
    log "Despliegue correcto: ${API_IMAGE}"
    exit 0
fi
fail "despliegue fallido (reversión: ${ROLLED_BACK}). Los datos pueden haber migrado: revise la copia previa antes de reintentar."
