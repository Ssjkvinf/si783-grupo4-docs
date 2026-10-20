#!/usr/bin/env bash
# Reversión MANUAL de la API a la imagen anterior (SE EJECUTA EN LA VM; lo invoca deploy.yml con action=rollback).
#
# Usa la etiqueta guardada por deploy_remote.sh en <REPORT_DIR>/previous_image.txt, o la imagen indicada en
# ROLLBACK_IMAGE (una etiqueta que exista localmente o en GHCR, p. ej. ghcr.io/…/framework-pruebas-sql:v0.9.0).
#
# Aviso: volver a una imagen anterior NO deshace cambios en la base. Si la versión que se retira migró el esquema,
# restaure la copia de seguridad previa (ver docs/operacion-fase3.md) con la API detenida.
#
# Variables obligatorias: APP_DIR. Opcionales: ROLLBACK_IMAGE, API_CONTAINER, HEALTH_TIMEOUT, REPORT_DIR, GHCR_USER, GHCR_TOKEN.
set -euo pipefail

: "${APP_DIR:?Falta APP_DIR}"
API_CONTAINER="${API_CONTAINER:-framework_api_prod}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-120}"
REPORT_DIR="${REPORT_DIR:-/opt/framework/releases}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }
fail() { echo "ERROR: $*" >&2; exit 1; }

TARGET="${ROLLBACK_IMAGE:-}"
if [ -z "$TARGET" ]; then
    [ -f "$REPORT_DIR/previous_image.txt" ] || fail "no hay imagen anterior registrada ($REPORT_DIR/previous_image.txt); indique ROLLBACK_IMAGE"
    TARGET="$(cat "$REPORT_DIR/previous_image.txt")"
fi
[ -f "$APP_DIR/compose.yml" ] && [ -f "$APP_DIR/.env.production" ] && [ -f "$APP_DIR/compose.release.yml" ] \
    || fail "faltan compose.yml, .env.production o compose.release.yml en $APP_DIR"

if ! docker image inspect "$TARGET" >/dev/null 2>&1; then
    if [ -n "${GHCR_TOKEN:-}" ] && [ -n "${GHCR_USER:-}" ]; then
        printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null
    fi
    log "Descargando $TARGET"
    docker pull "$TARGET" >/dev/null || fail "la imagen $TARGET no existe localmente ni en el registro"
fi

CURRENT_REF="$(docker inspect --format '{{.Config.Image}}' "$API_CONTAINER" 2>/dev/null || echo ninguna)"
log "Reversión: ${CURRENT_REF} → ${TARGET}"
export API_IMAGE="$TARGET"
docker compose -f "$APP_DIR/compose.yml" -f "$APP_DIR/compose.release.yml" --env-file "$APP_DIR/.env.production" up -d --no-build --no-deps api

deadline=$((SECONDS + HEALTH_TIMEOUT)); status=""
while [ "$SECONDS" -lt "$deadline" ]; do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}sin-healthcheck{{end}}' "$API_CONTAINER" 2>/dev/null || echo ausente)"
    [ "$status" = "healthy" ] && break
    sleep 3
done
mkdir -p "$REPORT_DIR"
printf '{ "fecha_utc": "%s", "reversion_a": "%s", "desde": "%s", "estado": "%s" }\n' "$STAMP" "$TARGET" "$CURRENT_REF" "$status" | tee "$REPORT_DIR/rollback_${STAMP}.json"
[ "$status" = "healthy" ] || fail "tras la reversión el contenedor no quedó saludable (estado: $status)"
log "Reversión correcta"
