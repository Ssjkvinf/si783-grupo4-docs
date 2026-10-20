#!/usr/bin/env bash
# Copia consistente de la SQLite de la aplicación en la VM (se ejecuta EN LA VM; lo invoca backup.yml por SSH
# o se lanza a mano). No detiene ni modifica la aplicación: abre el volumen en SOLO LECTURA y usa la API de
# respaldo de SQLite (ver scripts/backup/sqlite_backup.py).
#
# Variables (todas opcionales):
#   APP_VOLUME    volumen de Docker con la SQLite   (por defecto framework_pruebas_sql_framework_data)
#   BACKUP_DIR    carpeta de la VM donde se guarda  (por defecto /opt/framework/backups)
#   PYTHON_IMAGE  imagen con Python (por defecto python:3.12-slim; ya está en la VM porque la app se construye sobre ella)
#   KEEP_LOCAL    cuántas copias recientes se conservan en la VM (por defecto 14); las más antiguas se borran
#
# Uso: backup_vm.sh            -> crea <BACKUP_DIR>/framework_interno_<fecha>.sqlite.gz + manifiesto + reporte
set -euo pipefail

APP_VOLUME="${APP_VOLUME:-framework_pruebas_sql_framework_data}"
BACKUP_DIR="${BACKUP_DIR:-/opt/framework/backups}"
PYTHON_IMAGE="${PYTHON_IMAGE:-python:3.12-slim}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$BACKUP_DIR"
export MSYS_NO_PATHCONV=1

if ! docker volume inspect "$APP_VOLUME" >/dev/null 2>&1; then
    echo "ERROR: no existe el volumen '$APP_VOLUME'. Indique APP_VOLUME (docker volume ls)." >&2
    exit 2
fi

docker run --rm \
    -v "$APP_VOLUME":/data:ro \
    -v "$BACKUP_DIR":/backup \
    -v "$HERE":/scripts:ro \
    "$PYTHON_IMAGE" \
    python /scripts/sqlite_backup.py --db /data/framework_interno.db --out-dir /backup --gzip

# Retención local: conserva las KEEP_LOCAL copias más recientes (solo archivos de copia creados por este script).
KEEP_LOCAL="${KEEP_LOCAL:-14}"
ls -1t "$BACKUP_DIR"/framework_interno_*.sqlite.gz 2>/dev/null | tail -n +"$((KEEP_LOCAL + 1))" | while read -r old; do
    base="${old%.sqlite.gz}"
    rm -f -- "$old" "$base.manifest.json" "$base.reporte.md"
    echo "Copia antigua eliminada: $(basename "$old")"
done
