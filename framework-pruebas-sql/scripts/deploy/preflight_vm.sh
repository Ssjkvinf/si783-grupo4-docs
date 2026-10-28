#!/usr/bin/env bash
# Revisión previa de la VM (SOLO LECTURA). Kevin la ejecuta en la VM antes del primer despliegue de la versión nueva:
#   bash preflight_vm.sh                      # detecta la carpeta de la app desde el contenedor en marcha
#   APP_DIR=/ruta/de/la/app bash preflight_vm.sh
#
# Qué muestra: contenedores en ejecución, compose en uso (con o sin Caddy), espacio en disco, memoria, versión de Docker,
# si existe .env.production, si alguna variable usa un valor de ejemplo que la app bloquea (solo SÍ/NO por NOMBRE),
# APP_REGISTRATION_ENABLED, si la IP real llega detrás de Caddy, la versión de la base interna y si hay copias recientes.
#
# Garantías: no arranca, detiene, descarga ni borra nada; no escribe archivos; NUNCA imprime el valor de una variable
# secreta (las compara en memoria). Termina siempre con código 0; los problemas se listan al final como «REVISAR».
#
# Variables opcionales: APP_DIR, ENV_FILE (por defecto $APP_DIR/.env.production), API_CONTAINER (framework_api_prod),
# BACKUP_DIR (/opt/framework/backups), BACKUP_MAX_DAYS (7), MIN_FREE_GB (3).
set -u

API_CONTAINER="${API_CONTAINER:-framework_api_prod}"
BACKUP_DIR="${BACKUP_DIR:-/opt/framework/backups}"
BACKUP_MAX_DAYS="${BACKUP_MAX_DAYS:-7}"
MIN_FREE_GB="${MIN_FREE_GB:-3}"
REVISAR=()

titulo() { printf '\n== %s ==\n' "$1"; }
revisar() { REVISAR+=("$1"); }

# Valores de ejemplo que la aplicación se niega a usar (app/security/auth.py: SECRETOS_DE_EJEMPLO y CLAVES_DE_EJEMPLO).
BLOQUEADOS_APP_SESSION_SECRET="default_insecure_secret_replace_in_prod secreto_ficticio_largo_y_complejo"
BLOQUEADOS_APP_ACCESS_PASSWORD="contrasena_ficticia"
# Otros valores de ejemplo de infra/production/.env.production.example (la app no los bloquea, pero no deben usarse).
EJEMPLO_OTROS="APP_ACCESS_USERNAME=usuario_ficticio ORACLE_PWD=contrasena_ficticia_admin FRAMEWORK_TEST_PASSWORD=contrasena_ficticia_test APP_DOMAIN=dominio.pendiente.com CORS_ORIGINS=https://dominio.pendiente.com"

# Lee el valor de NOMBRE de un texto KEY=VALUE (sin imprimirlo). Quita comillas y espacios de los extremos.
valor_de() {
    local nombre="$1" texto="$2" linea v
    linea="$(printf '%s\n' "$texto" | grep -E "^[[:space:]]*(export[[:space:]]+)?${nombre}=" | tail -n 1)" || true
    [ -z "$linea" ] && return 1
    v="${linea#*=}"
    v="${v%$'\r'}"
    v="${v#\"}"; v="${v%\"}"; v="${v#\'}"; v="${v%\'}"
    v="$(printf '%s' "$v" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
    printf '%s' "$v"
}

# en_lista VALOR "a b c": devuelve 0 si VALOR (sin distinguir mayúsculas) está en la lista.
en_lista() {
    local v x
    v="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
    for x in $2; do [ "$v" = "$x" ] && return 0; done
    return 1
}

# ------------------------------------------------------------------ Docker
titulo "Docker"
if ! command -v docker >/dev/null 2>&1; then
    echo "docker: NO instalado"
    revisar "Docker no está instalado o no está en el PATH."
    printf '\n== Resumen ==\nREVISAR:\n'; printf ' - %s\n' "${REVISAR[@]}"; exit 0
fi
echo "Versión del motor: $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'no disponible (¿permisos? use sudo o el grupo docker)')"
echo "Compose: $(docker compose version --short 2>/dev/null || echo 'plugin docker compose NO disponible')"
docker compose version >/dev/null 2>&1 || revisar "Falta el plugin «docker compose» (lo usan deploy_remote.sh y rollback_remote.sh)."

titulo "Contenedores en ejecución"
docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}' 2>/dev/null || echo "no se pudieron listar"

titulo "Compose en uso"
if docker inspect "$API_CONTAINER" >/dev/null 2>&1; then
    proyecto="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$API_CONTAINER" 2>/dev/null)"
    carpeta="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' "$API_CONTAINER" 2>/dev/null)"
    archivos="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$API_CONTAINER" 2>/dev/null)"
    echo "Contenedor de la API: $API_CONTAINER"
    echo "Imagen en uso: $(docker inspect --format '{{.Config.Image}}' "$API_CONTAINER" 2>/dev/null)"
    echo "Salud: $(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}sin healthcheck{{end}}' "$API_CONTAINER" 2>/dev/null)"
    echo "Proyecto compose: ${proyecto:-(no creado con compose)}"
    echo "Carpeta del compose: ${carpeta:-(desconocida)}"
    echo "Archivos de compose: ${archivos:-(desconocidos)}"
    echo "Volúmenes montados en la API: $(docker inspect --format '{{range .Mounts}}{{.Name}} en {{.Destination}}; {{end}}' "$API_CONTAINER" 2>/dev/null)"
    echo "  (Si reemplaza compose.yml en la VM, el proyecto y el volumen de /data deben seguir siendo estos; si no, la app arrancaría con una base vacía.)"
    APP_DIR="${APP_DIR:-$carpeta}"
    publicados="$(docker port "$API_CONTAINER" 2>/dev/null)"
    if [ -n "$publicados" ]; then
        echo "Puertos publicados por la API: SÍ"
        revisar "La API publica puertos al exterior: con FORWARDED_ALLOW_IPS=* alguien podría falsear su IP. Solo Caddy debería alcanzarla."
    else
        echo "Puertos publicados por la API: NO (solo accesible dentro de la red de Docker)"
    fi
else
    echo "No hay un contenedor llamado $API_CONTAINER (indique API_CONTAINER si se llama distinto)."
    revisar "No se encontró el contenedor de la API ($API_CONTAINER)."
fi
caddy="$(docker ps --format '{{.Names}} {{.Image}}' 2>/dev/null | grep -i caddy | head -n 1)"
if [ -n "$caddy" ]; then echo "Caddy: SÍ (${caddy%% *})"; else echo "Caddy: NO (no hay un contenedor de Caddy en marcha)"; revisar "No se ve Caddy en marcha: confirme cómo llega HTTPS a la aplicación."; fi

# ------------------------------------------------------------------ Recursos
titulo "Espacio en disco"
df -h / 2>/dev/null | sed -n '1,2p'
[ -d /var/lib/docker ] && df -h /var/lib/docker 2>/dev/null | sed -n '2p'
libre_kb="$(df -Pk / 2>/dev/null | awk 'NR==2 {print $4}')"
if [ -n "$libre_kb" ] && [ "$libre_kb" -lt $((MIN_FREE_GB * 1024 * 1024)) ] 2>/dev/null; then
    revisar "Quedan menos de ${MIN_FREE_GB} GB libres en /: la imagen nueva y las copias pueden no caber."
fi

titulo "Memoria"
if command -v free >/dev/null 2>&1; then
    free -m | sed -n '1,2p'
elif [ -r /proc/meminfo ]; then
    grep -E '^(MemTotal|MemAvailable):' /proc/meminfo
else
    echo "no disponible"
fi

# ------------------------------------------------------------------ Configuración (sin imprimir valores)
titulo "Archivo .env de producción"
ENV_FILE="${ENV_FILE:-${APP_DIR:+$APP_DIR/.env.production}}"
ENV_TXT=""
if [ -n "${ENV_FILE:-}" ] && [ -f "$ENV_FILE" ]; then
    echo "Existe: SÍ ($ENV_FILE)"
    ENV_TXT="$(cat "$ENV_FILE" 2>/dev/null)"
else
    echo "Existe: NO (${ENV_FILE:-no se pudo deducir la carpeta; indique APP_DIR})"
    revisar "No se encontró .env.production: deploy_remote.sh lo necesita."
fi
CONT_TXT="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "$API_CONTAINER" 2>/dev/null)" || CONT_TXT=""

titulo "Valores de ejemplo (solo SÍ/NO; los valores no se muestran)"
for nombre in APP_SESSION_SECRET APP_ACCESS_PASSWORD; do
    lista_var="BLOQUEADOS_${nombre}"
    for origen in archivo contenedor; do
        if [ "$origen" = archivo ]; then texto="$ENV_TXT"; else texto="$CONT_TXT"; fi
        [ -z "$texto" ] && continue
        if v="$(valor_de "$nombre" "$texto")"; then
            if en_lista "$v" "${!lista_var}"; then
                echo "$nombre ($origen): usa un valor de ejemplo BLOQUEADO por la app: SÍ"
                revisar "$nombre ($origen) usa un valor de ejemplo: la versión nueva responderá 503 hasta cambiarlo."
            else
                echo "$nombre ($origen): usa un valor de ejemplo bloqueado: NO"
            fi
        else
            echo "$nombre ($origen): no definida"
        fi
    done
done
for par in $EJEMPLO_OTROS; do
    nombre="${par%%=*}"; ejemplo="${par#*=}"
    if [ -n "$ENV_TXT" ] && v="$(valor_de "$nombre" "$ENV_TXT")" && [ "$v" = "$ejemplo" ]; then
        echo "$nombre (archivo): usa el valor del archivo de ejemplo: SÍ"
        revisar "$nombre usa el valor del archivo de ejemplo."
    fi
done

titulo "Registro y proxy"
reg=""
if [ -n "$ENV_TXT" ] && reg="$(valor_de APP_REGISTRATION_ENABLED "$ENV_TXT")"; then
    echo "APP_REGISTRATION_ENABLED (archivo): $reg"
else
    echo "APP_REGISTRATION_ENABLED (archivo): no definida"
fi
if [ -n "$CONT_TXT" ] && regc="$(valor_de APP_REGISTRATION_ENABLED "$CONT_TXT")"; then
    echo "APP_REGISTRATION_ENABLED (contenedor): $regc"
else
    echo "APP_REGISTRATION_ENABLED (contenedor): no definida (la versión nueva usa true por defecto si compose.yml no la fija)"
fi
[ "$(printf '%s' "${reg:-}" | tr '[:upper:]' '[:lower:]')" = "false" ] || revisar "Recomendado en producción: APP_REGISTRATION_ENABLED=false (las cuentas las crea un ADMIN)."
if [ -n "$CONT_TXT" ] && valor_de FORWARDED_ALLOW_IPS "$CONT_TXT" >/dev/null; then
    echo "FORWARDED_ALLOW_IPS en el contenedor: SÍ"
else
    echo "FORWARDED_ALLOW_IPS en el contenedor: NO"
    revisar "Sin FORWARDED_ALLOW_IPS la app ve a todos con la IP de Caddy: actualice compose.yml de la VM con el del repositorio antes de desplegar."
fi

# ------------------------------------------------------------------ Datos
titulo "Base interna (solo lectura)"
ver="$(docker exec "$API_CONTAINER" python -c "import sqlite3;c=sqlite3.connect('file:/data/framework_interno.db?mode=ro',uri=True);print(c.execute('select version_num from alembic_version').fetchone()[0])" 2>/dev/null)"
if [ -n "$ver" ]; then
    echo "Versión de Alembic: $ver"
    [ "$ver" = "a4b8c2d9e1f0" ] || echo "La versión nueva aplicará migraciones al arrancar (usuarios y «ejecutado por»): haga una copia antes."
else
    echo "Versión de Alembic: no disponible"
fi

titulo "Copias de seguridad"
if [ -d "$BACKUP_DIR" ]; then
    total="$(find "$BACKUP_DIR" -maxdepth 1 -name 'framework_interno_*.sqlite.gz' 2>/dev/null | wc -l | tr -d ' ')"
    recientes="$(find "$BACKUP_DIR" -maxdepth 1 -name 'framework_interno_*.sqlite.gz' -mtime -"$BACKUP_MAX_DAYS" 2>/dev/null | wc -l | tr -d ' ')"
    ultima="$(ls -1t "$BACKUP_DIR"/framework_interno_*.sqlite.gz 2>/dev/null | head -n 1)"
    echo "Carpeta: $BACKUP_DIR · copias: $total · de los últimos $BACKUP_MAX_DAYS días: $recientes"
    [ -n "$ultima" ] && echo "Más reciente: $(basename "$ultima")"
    [ "$recientes" -gt 0 ] 2>/dev/null || revisar "No hay copias de los últimos $BACKUP_MAX_DAYS días: ejecute el flujo de copia antes de desplegar."
else
    echo "La carpeta $BACKUP_DIR no existe (todavía no se hizo ninguna copia)."
    revisar "No hay copias de seguridad en $BACKUP_DIR."
fi

# ------------------------------------------------------------------ Resumen
titulo "Resumen"
if [ "${#REVISAR[@]}" -eq 0 ]; then
    echo "Todo en orden para continuar."
else
    echo "REVISAR antes de desplegar (${#REVISAR[@]}):"
    printf ' - %s\n' "${REVISAR[@]}"
fi
echo "(Este script no cambió nada en la VM.)"
exit 0
