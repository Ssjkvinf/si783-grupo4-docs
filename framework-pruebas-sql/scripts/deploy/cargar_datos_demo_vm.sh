#!/usr/bin/env bash
# Carga los 5 productos de demostración en FRAMEWORK_TEST_ITEMS del Oracle de la VM (framework_oracle_prod).
#
# Qué hace: entra al contenedor con `docker exec` (no lo reinicia ni lo recrea) y ejecuta infra/oracle/demo/seed_demo_data.sql
# como FRAMEWORK_TEST. La contraseña se lee DENTRO del contenedor (su variable FRAMEWORK_TEST_PASSWORD): no se pide, no se
# imprime y no viaja por la línea de comandos.
# Es idempotente: borra las filas de esa tabla de demostración y vuelve a cargar las mismas 5. No toca la base interna de la app.
# Uso (en la VM): bash cargar_datos_demo_vm.sh  [ruta de seed_demo_data.sql; por defecto el del repositorio desplegado]
set -euo pipefail

CONTENEDOR="${ORACLE_CONTAINER:-framework_oracle_prod}"
SEED="${1:-$(dirname "$0")/../../infra/oracle/demo/seed_demo_data.sql}"

[ -f "$SEED" ] || { echo "No se encontró el archivo de datos: $SEED" >&2; exit 1; }
docker inspect "$CONTENEDOR" >/dev/null 2>&1 || { echo "No existe el contenedor $CONTENEDOR" >&2; exit 1; }

docker exec -i "$CONTENEDOR" bash -c 'sqlplus -s "FRAMEWORK_TEST/\"${FRAMEWORK_TEST_PASSWORD}\"@//localhost:1521/FREEPDB1"' < "$SEED"
