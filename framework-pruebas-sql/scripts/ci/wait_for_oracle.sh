#!/usr/bin/env bash
# Espera a que un Oracle desechable (imagen gvenzl/oracle-free en un contenedor) ACEPTE CONEXIONES con el usuario de la
# aplicación, y si no lo logra imprime un diagnóstico útil. Lo usan db-objects.yml y sql-checks.yml.
#
# Por qué no se usa `docker inspect .State.Health`: el contenedor se crea sin --health-cmd, así que Docker no tiene estado de
# salud que consultar y esa espera nunca terminaría aunque la base esté lista (el README de gvenzl pasa --health-cmd
# healthcheck.sh de forma explícita). Aquí se sondea lo que de verdad hace falta: iniciar sesión como FRAMEWORK_TEST.
#
# Uso (la contraseña ya debe estar en el entorno de ese paso; aquí no se escribe ningún valor):
#   bash scripts/ci/wait_for_oracle.sh <contenedor> [segundos_maximos]
# Variables (todas opcionales salvo la contraseña): ORACLE_WAIT_MAX_SECONDS (900), ORACLE_WAIT_INTERVAL (10),
#   ORACLE_WAIT_USER (FRAMEWORK_TEST), ORACLE_WAIT_SERVICE (FREEPDB1).
# La contraseña se lee del entorno y NUNCA se imprime (ni como argumento ni en los diagnósticos).
# Códigos de salida: 0 listo · 1 no estuvo listo a tiempo o el contenedor se detuvo · 2 uso incorrecto.
set -u

CONTAINER="${1:-}"
MAX="${2:-${ORACLE_WAIT_MAX_SECONDS:-900}}"
INTERVAL="${ORACLE_WAIT_INTERVAL:-10}"
ORA_USER="${ORACLE_WAIT_USER:-FRAMEWORK_TEST}"
ORA_SERVICE="${ORACLE_WAIT_SERVICE:-FREEPDB1}"
[ -n "$CONTAINER" ] || { echo "Uso: wait_for_oracle.sh <contenedor> [segundos_maximos]" >&2; exit 2; }
[ -n "${FRAMEWORK_TEST_PASSWORD:-}" ] || { echo "ERROR: falta FRAMEWORK_TEST_PASSWORD en el entorno" >&2; exit 2; }

start=$SECONDS
attempts=0
last_error="(sin sondeos todavía)"
ready_seen_at=""

ocultar() {   # quita la contraseña de cualquier texto antes de imprimirlo
    local t="$1"
    printf '%s' "${t//"$FRAMEWORK_TEST_PASSWORD"/***}"
}

diagnostico() {
    local motivo="$1"
    echo "::group::Diagnóstico de Oracle (${motivo})"
    echo "Contenedor: ${CONTAINER} · usuario de sondeo: ${ORA_USER} · servicio: ${ORA_SERVICE}"
    echo "Tiempo esperado: $((SECONDS - start)) s de ${MAX} s · sondeos: ${attempts} · intervalo: ${INTERVAL} s"
    echo "Último error del sondeo: $(ocultar "$last_error")"
    if [ -n "$ready_seen_at" ]; then
        echo "El log del contenedor mostró «DATABASE IS READY TO USE!» a los ${ready_seen_at} s (pero el inicio de sesión de sondeo no funcionó: revise usuario, contraseña y servicio)"
    else
        echo "El log del contenedor NO mostró «DATABASE IS READY TO USE!»"
    fi
    echo "--- estado del contenedor"
    docker inspect -f 'Estado={{.State.Status}} Código={{.State.ExitCode}} SinMemoria={{.State.OOMKilled}} Salud={{if .State.Health}}{{.State.Health.Status}}{{else}}sin-healthcheck{{end}} Inicio={{.State.StartedAt}}' "$CONTAINER" 2>&1 | head -5
    docker ps -a --filter "name=${CONTAINER}" 2>&1 | head -5
    echo "--- últimas 80 líneas del log del contenedor"
    docker logs --tail 80 "$CONTAINER" 2>&1 | while IFS= read -r l; do ocultar "$l"; echo; done
    echo "--- recursos del ejecutor"
    df -h / 2>/dev/null | head -3
    free -m 2>/dev/null | head -3
    docker stats --no-stream "$CONTAINER" 2>&1 | head -3
    echo "::endgroup::"
    echo "::error::Oracle no estuvo listo (${motivo}). Último error: $(ocultar "$last_error")"
}

echo "Esperando a Oracle en ${CONTAINER} (hasta ${MAX} s; sondeo cada ${INTERVAL} s con el usuario ${ORA_USER})"
while [ $((SECONDS - start)) -lt "$MAX" ]; do
    estado="$(docker inspect -f '{{.State.Status}}' "$CONTAINER" 2>&1)"
    if [ "$estado" != "running" ]; then
        last_error="el contenedor no está en ejecución (estado: ${estado})"
        diagnostico "contenedor detenido"
        exit 1
    fi
    if [ -z "$ready_seen_at" ] && docker logs "$CONTAINER" 2>&1 | grep -q "DATABASE IS READY TO USE"; then
        ready_seen_at=$((SECONDS - start))
        echo "  [${ready_seen_at} s] el log del contenedor ya dice «DATABASE IS READY TO USE!»; se confirma con un inicio de sesión"
    fi
    attempts=$((attempts + 1))
    cmd="sqlplus -L -s \"${ORA_USER}/\${FRAMEWORK_TEST_PASSWORD}@//localhost:1521/${ORA_SERVICE}\""
    salida="$(printf '%s\n' 'SET HEADING OFF FEEDBACK OFF PAGESIZE 0' 'SELECT 1 FROM dual;' 'EXIT' \
        | docker exec -i -e FRAMEWORK_TEST_PASSWORD "$CONTAINER" bash -c "$cmd" 2>&1)"
    if printf '%s\n' "$salida" | grep -qE '^[[:space:]]*1[[:space:]]*$'; then
        echo "Oracle listo: el usuario ${ORA_USER} inició sesión a los $((SECONDS - start)) s (sondeo ${attempts})"
        exit 0
    fi
    last_error="$(printf '%s' "$salida" | tr -s '\r\n' '  ' | cut -c1-300)"
    [ -n "$last_error" ] || last_error="sin salida de sqlplus"
    echo "  [$((SECONDS - start)) s] aún no acepta conexiones (sondeo ${attempts}): $(ocultar "$last_error")"
    sleep "$INTERVAL"
done

diagnostico "tiempo agotado"
exit 1
