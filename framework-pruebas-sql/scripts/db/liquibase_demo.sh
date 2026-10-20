#!/usr/bin/env bash
# Aplica los changelogs de Liquibase (infra/oracle/liquibase) DOS veces contra un Oracle y guarda los registros.
# La segunda ejecución no debe aplicar nada: así se comprueba la idempotencia.
#
# Es para un Oracle de pruebas/desechable al que ya se puede llegar desde Docker (misma red o --network host).
# NO contiene credenciales: las lee del entorno y no las imprime.
#
# Variables de entorno obligatorias:
#   LB_NETWORK    red de Docker desde la que se ve Oracle (en GitHub Actions: host)
#   LB_JDBC_URL   p. ej. jdbc:oracle:thin:@//oracle:1521/FREEPDB1
#   LB_USER       cuenta dueña del esquema (FRAMEWORK_TEST)
#   LB_PASSWORD   su contraseña
# Opcionales: LB_CONTEXTS (por defecto esquema,demo), LIQUIBASE_IMAGE (por defecto liquibase/liquibase:4.33)
#
# Uso: scripts/db/liquibase_demo.sh <carpeta_de_salida>
set -euo pipefail

OUT="${1:?Indique la carpeta de salida}"
: "${LB_NETWORK:?Falta LB_NETWORK}" "${LB_JDBC_URL:?Falta LB_JDBC_URL}" "${LB_USER:?Falta LB_USER}" "${LB_PASSWORD:?Falta LB_PASSWORD}"
CONTEXTS="${LB_CONTEXTS:-esquema,demo}"
IMAGE="${LIQUIBASE_IMAGE:-liquibase/liquibase:4.33}"

# Guardia: el contexto «demo» BORRA y recarga FRAMEWORK_TEST_ITEMS. Solo contra un Oracle local o de CI (misma regla que tests/oracle_guard.py).
#   - siempre: localhost y loopback; solo en GitHub Actions: oracle, fw_ci_oracle, fw_chk_oracle;
#   - cualquier otro host: ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST=<nombre exacto del host> (confirmación explícita).
DB_HOST="$(printf '%s' "$LB_JDBC_URL" | sed -n 's#.*@/*\([^:/]*\).*#\1#p' | tr 'A-Z' 'a-z')"
case ",$CONTEXTS," in
    *,demo,*)
        permitido=0
        case "$DB_HOST" in localhost|127.*) permitido=1 ;; esac
        if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
            case "$DB_HOST" in oracle|fw_ci_oracle|fw_chk_oracle) permitido=1 ;; esac
        fi
        CONFIRMADO="$(printf '%s' "${ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST:-}" | tr 'A-Z' 'a-z')"
        if [ -n "$DB_HOST" ] && [ "$CONFIRMADO" = "$DB_HOST" ]; then permitido=1; fi
        if [ "$permitido" != "1" ]; then
            echo "ERROR: el contexto «demo» borra datos y el host '${DB_HOST:-?}' no es local ni de CI. No se ejecuta nada." >&2
            echo "Si es un Oracle desechable, defina ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST=${DB_HOST:-<host>} (nombre exacto), o use LB_CONTEXTS=esquema." >&2
            exit 3
        fi
        ;;
esac
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHANGELOG_DIR="$(cd "$HERE/../../infra/oracle/liquibase" && pwd)"

mkdir -p "$OUT"
export LIQUIBASE_COMMAND_URL="$LB_JDBC_URL" LIQUIBASE_COMMAND_USERNAME="$LB_USER" LIQUIBASE_COMMAND_PASSWORD="$LB_PASSWORD"
export MSYS_NO_PATHCONV=1   # Git Bash en Windows: no reescribir rutas del contenedor

lb() {
    docker run --rm --network "$LB_NETWORK" \
        -e LIQUIBASE_COMMAND_URL -e LIQUIBASE_COMMAND_USERNAME -e LIQUIBASE_COMMAND_PASSWORD \
        -v "$CHANGELOG_DIR:/liquibase/project:ro" -w /liquibase/project \
        "$IMAGE" --defaults-file=liquibase.properties "$@"
}

echo "== Liquibase: validar changelogs"
lb validate --contexts="$CONTEXTS" >"$OUT/00_validate.log" 2>&1 || { cat "$OUT/00_validate.log"; exit 1; }

echo "== Liquibase: primera ejecución (update)"
lb update --contexts="$CONTEXTS" >"$OUT/01_update_1.log" 2>&1 || { cat "$OUT/01_update_1.log"; exit 1; }

echo "== Liquibase: segunda ejecución (update) -> no debe aplicar cambios"
lb update --contexts="$CONTEXTS" >"$OUT/02_update_2.log" 2>&1 || { cat "$OUT/02_update_2.log"; exit 1; }

echo "== Liquibase: historial y estado"
lb history >"$OUT/03_history.log" 2>&1 || true
lb status --verbose --contexts="$CONTEXTS" >"$OUT/04_status.log" 2>&1 || true

echo "Registros guardados en $OUT"
