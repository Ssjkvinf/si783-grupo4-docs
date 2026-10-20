# Demostración de la Fase 2: reglas sobre datos, suite repetible y evidencia

Todo esto se hace en **un Oracle local desechable** (Docker en su PC). No use la VM de Azure ni una base real: el escenario carga y modifica datos de demostración.

## 1. Qué cambia respecto a un `SELECT` aislado

Una persona puede definir **reglas** sobre sus datos, agruparlas en una **suite** y **repetirla** con un clic. Cada ejecución guarda la evidencia (qué se esperaba, qué se obtuvo, estado, fecha) en el historial.

Hay tres formas de comprobar el resultado de una consulta; no son lo mismo:

| Validación | Qué compara | Ejemplo | Resultado |
| --- | --- | --- | --- |
| `ROW_COUNT` (cantidad de filas) | **Cuántas filas** devuelve la consulta | `SELECT ID FROM T WHERE ACTIVE = 1` esperando 4 | PASS si devuelve 4 filas |
| `SCALAR_VALUE` (valor que devuelve la consulta) | El **valor** de la primera columna de la **única fila** | `SELECT COUNT(*) FROM T WHERE NAME IS NULL` esperando 0 | PASS si el número calculado es 0 |
| `EXISTS` (existencia) | Si devuelve **al menos una fila** (`true`) o **ninguna** (`false`) | `SELECT ID FROM T WHERE ID = 3` esperando `true` | PASS si existe |

**La confusión que se corrigió:** un `COUNT(*)` siempre devuelve **1 fila**. Con `ROW_COUNT = 1` esa consulta pasa siempre, aunque el número que calcula sea 3 o 0. Para comparar el número hay que usar `SCALAR_VALUE`. La pantalla «Inicio» avisa cuando detecta `COUNT(...)` con «cantidad de filas» y ofrece cambiar a «valor», y las explicaciones de los resultados lo aclaran.

`SCALAR_VALUE` exige exactamente una fila (0 filas o varias dan FAIL, con explicación), compara números como números (`0`, `0.0` y `00` son iguales) y el texto de forma exacta; `NULL` representa el valor nulo. **No está disponible en ambientes PRODUCTION**, porque allí las filas se ocultan: se rechaza antes de ejecutar y se explica por qué.

## 2. Datos y reglas de demostración

La tabla ya existía: `FRAMEWORK_TEST_ITEMS` (`ID NUMBER PK`, `NAME VARCHAR2(100) NOT NULL`, `ACTIVE NUMBER(1) DEFAULT 1 NOT NULL`), creada por `infra/oracle/init/001_test_schema.sh` **vacía**. Los datos de ejemplo los carga `infra/oracle/demo/seed_demo_data.sql` (5 productos: Cuaderno, Lapicero, Regla, Borrador inactivo, Tijera).

Suite **«Demo: reglas de calidad de FRAMEWORK_TEST_ITEMS»** (todas deben pasar con esos datos):

| Regla | Validación | Esperado |
| --- | --- | --- |
| Hay 5 productos registrados (`COUNT(*)`) | valor | 5 |
| No hay productos sin nombre (`WHERE TRIM(NAME) IS NULL`) | valor | 0 |
| `ACTIVE` solo vale 0 o 1 (`WHERE ACTIVE NOT IN (0, 1)`) | valor | 0 |
| Hay 4 productos activos | valor | 4 |
| Existe el producto con ID 3 | existencia | true |

Suite **«Demo: ejemplos de FAIL y ERROR (intencionales)»**: se esperan 6 productos (hay 5 → FAIL) y una consulta sobre una tabla inexistente (ORA-00942 → ERROR).

## 3. Reproducirlo en su PC (Windows, PowerShell)

Todos los comandos se ejecutan desde `framework-pruebas-sql/`. No se tocan sus otros contenedores ni volúmenes.

### 3.1 Oracle desechable
```powershell
Copy-Item .env.oracle.example .env.oracle        # y cambie las dos contraseñas por valores propios
cd infra\oracle
docker compose up -d
docker compose ps                                 # espere "healthy" (1 a 3 minutos)
cd ..\..
```
Los scripts `.sh` deben tener finales de línea LF para ejecutarse dentro del contenedor; el repositorio lo fuerza con `.gitattributes`. Si su copia es anterior, vuelva a clonar o convierta `infra\oracle\init\001_test_schema.sh` a LF.

### 3.2 Cargar los datos de demostración
```powershell
Get-Content infra\oracle\demo\seed_demo_data.sql | docker exec -i framework_oracle_db bash -c 'sqlplus -s FRAMEWORK_TEST/"$FRAMEWORK_TEST_PASSWORD"@//localhost:1521/FREEPDB1'
```
Debe imprimir `Datos de demostracion cargados: 5 productos, 4 activos.` El script es idempotente: sirve también para **restaurar** los datos. (En bash: `docker exec -i framework_oracle_db bash -c '…' < infra/oracle/demo/seed_demo_data.sql`.)

La contraseña no se escribe en la línea de comandos: se lee de la variable de entorno del propio contenedor.

### 3.3 Aplicación
```powershell
python -m venv venv ; .\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --port 8001
```
(Se usa el puerto 8001 por si ya tiene otra aplicación en el 8000.) Abra `http://127.0.0.1:8001/ui/`.

### 3.4 Recorrido en la interfaz
1. En **Inicio → Conectar**: «Nueva conexión» con host `localhost`, puerto `1521`, servicio `FREEPDB1`, usuario `FRAMEWORK_TEST`, ambiente `TEST`; escriba la contraseña (la que puso en `.env.oracle`).
2. **Una comprobación suelta:** elija «Contar los registros de la tabla de demostración» (valor 5) → *Ejecutar* → **PASS**. Cambie el esperado a 4 → **FAIL** («esperabas 4 y devolvió 5»). Escriba `SELECT * FROM TABLA_QUE_NO_EXISTE` → **ERROR** (ORA-00942).
3. **La confusión de COUNT:** elija «Cantidad de filas…» con `SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS` y esperado 1: aparece el aviso azul y, tras ejecutar, la nota explica que se contó una fila, no el número.
4. **Suite repetible:** «Cargar las suites de demostración» → «Ejecutar la suite de reglas» → 5 PASS, con regla, esperado, obtenido y motivo. «Ejecutar de nuevo» repite sin reconstruir nada. «Ver un ejemplo de FAIL y ERROR» muestra los otros dos estados.
5. **Provocar un FAIL real y repararlo:**
   ```powershell
   "UPDATE FRAMEWORK_TEST_ITEMS SET ACTIVE = 7 WHERE ID = 4;`nCOMMIT;`nEXIT" | docker exec -i framework_oracle_db bash -c 'sqlplus -s FRAMEWORK_TEST/"$FRAMEWORK_TEST_PASSWORD"@//localhost:1521/FREEPDB1'
   ```
   Vuelva a ejecutar la suite: «ACTIVE solo vale 0 o 1» da **FAIL** (obtuvo 1). Restaure con el script del paso 3.2 y ejecútela otra vez: 5 PASS. En **Historial** quedan todas las ejecuciones.

## 4. Verificación automática contra Oracle (SELECT, INSERT con rollback, DROP rechazado)

Se prueba contra el Oracle desechable, consultando **desde una conexión independiente**. Defina las variables solo en esa sesión de PowerShell:
```powershell
$env:RUN_ORACLE_TESTS = "1"; $env:ORACLE_HOST = "127.0.0.1"; $env:ORACLE_PORT = "1521"; $env:ORACLE_SERVICE = "FREEPDB1"
$env:FRAMEWORK_TEST_PASSWORD = "<la de .env.oracle>"
$env:ORACLE_PWD = "<contraseña de SYS del Oracle desechable>"   # solo para crear las cuentas de privilegios mínimos
python -m pytest -m oracle_integration -v -s
```
**Guardia (Fase 7):** estas pruebas borran filas y crean cuentas, por eso solo corren contra un Oracle **local** (`localhost` o loopback) o de CI. Con otro `ORACLE_HOST` se **omiten sin conectar** y explican por qué. Si de verdad es un Oracle desechable remoto, defina `$env:ORACLE_TESTS_CONFIRM_DESTRUCTIVE_HOST = "<nombre exacto del host>"` (no existe un comodín). El script `scripts/db/liquibase_demo.sh` aplica la misma regla cuando se pide el contexto `demo` (que borra y recarga la tabla); con `LB_CONTEXTS=esquema` no hace falta confirmación. `-s` muestra las líneas `[EVIDENCIA …]`. Sin `ORACLE_PWD` las pruebas de privilegios mínimos se omiten (no cuentan como aprobadas).

Qué comprueban:
- **INSERT en TEST con ROLLBACK:** cuenta `FW_TEST_MIN` (solo `CREATE SESSION` + `SELECT, INSERT` sobre `FW_OWNER.CANARY`). Filas antes = 3 → la aplicación ejecuta el `INSERT` (rowcount 1, `rollback_applied = True`) → filas después = 3 y 0 filas con el ID insertado, medido con otra conexión. Un control negativo (un `INSERT` + `COMMIT` fuera de la aplicación) demuestra que la medición sí detecta una fila que permanece.
- **DROP rechazado:** `DROP TABLE`, `TRUNCATE`, `ALTER` y «dos sentencias en una» terminan en ERROR («Rechazado…») con **0 conexiones abiertas a Oracle**; la tabla sigue existiendo con sus 3 filas. La cuenta no tiene `DROP`/`DELETE`/`UPDATE`/`ALTER` ni roles (se comprueba en el diccionario de datos). **No se ejecuta ningún `DROP` real.**
- **Suite:** 5 PASS → dato roto → 4 PASS + 1 FAIL → dato corregido → 5 PASS; 15 registros en el historial.

Pruebas sin Oracle (Oracle simulado): `python -m pytest -m "not oracle_integration"`. Son pruebas de lógica y de interfaz; **no sustituyen a las de Oracle real**.

## 5. Limitaciones (importante)

- **El rollback no es una garantía universal.** Funciona aquí porque la sentencia es un `INSERT`/`UPDATE`/`DELETE` simple, sin `COMMIT` implícito. No revierte, por ejemplo: el avance de una **secuencia** (`NEXTVAL`), lo que haga un **trigger o función con transacción autónoma**, llamadas a paquetes que escriban fuera de la transacción (`UTL_*`, `DBMS_*`, enlaces a otras bases) ni, por supuesto, **DDL** (que Oracle confirma solo; por eso se bloquea). El análisis de la sentencia es léxico (`sqlparse`): para entornos reales hay que usar cuentas Oracle de **privilegios mínimos**.
- Las pruebas de privilegios mínimos demuestran el comportamiento con esas cuentas en Oracle Free 23ai en Docker; no certifican otras versiones ni configuraciones.
- Los datos de demostración y las suites son de ejemplo. Las reglas esperan exactamente los datos de `seed_demo_data.sql`; las pruebas `oracle_integration` existentes (`test_oracle_integration.py`) **vacían y recargan** `FRAMEWORK_TEST_ITEMS`; vuelva a ejecutar el paso 3.2 después de correrlas.
- `SCALAR_VALUE` no existe en PRODUCTION (filas ocultas).
- Las capturas y resultados de esta demostración provienen de un Oracle local desechable, no de la VM de Azure.

## 6. Qué guardar como evidencia

1. Captura de «Inicio» con una comprobación de valor (PASS) y otra FAIL con la explicación.
2. Captura del aviso de `COUNT(...)` con «cantidad de filas» y de la nota posterior.
3. Captura de la suite de reglas: 5 PASS con regla / esperado / obtenido.
4. Captura de la suite tras provocar el dato inválido (1 FAIL) y tras repararlo (5 PASS), y del historial.
5. Salida de `pytest -m oracle_integration -v -s` con las líneas `[EVIDENCIA INSERT]`, `[EVIDENCIA DDL]` y `[EVIDENCIA SUITE]`.
