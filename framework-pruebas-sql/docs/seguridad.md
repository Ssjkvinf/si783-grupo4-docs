# Seguridad

## Autenticación, usuarios y roles
Con `APP_ACCESS_ENABLED=true` la aplicación exige ingresar con una cuenta individual (`app/api/users.py`, `app/security/auth.py`, `app/security/acceso.py`).

- **Primer administrador:** se crea al primer ingreso con `APP_ACCESS_USERNAME` y `APP_ACCESS_PASSWORD` si todavía no existe. Después la contraseña se cambia desde la aplicación («Cambiar mi contraseña»); cambiar la variable de entorno ya no la modifica. Si la contraseña inicial no cumple la política, la interfaz pide cambiarla.
- **Roles:** `ADMIN` aprueba solicitudes, asigna roles y contraseñas, y crea, modifica o elimina proyectos y conexiones. `TESTER` usa las conexiones existentes para crear y ejecutar casos y suites, usar el asistente, Excel e historial. El servidor aplica el rol en cada ruta (403); la interfaz solo oculta los botones.
- **Solicitud de cuenta:** la pantalla de ingreso permite «Solicitar acceso». La cuenta queda como `TESTER` **inactiva** hasta que un `ADMIN` la aprueba. Se desactiva con `APP_REGISTRATION_ENABLED=false`. Máximo 10 solicitudes por IP y hora.
- **Contraseñas:** solo se guarda un hash PBKDF2-HMAC-SHA256 con sal aleatoria (`PASSWORD_HASH_ITERATIONS`, por defecto 260 000) y se comparan en tiempo constante. Política: al menos 10 caracteres, letras y números, sin contener el usuario.
- **Sesión:** cookie `HttpOnly`, `SameSite=Strict`, `Secure` cuando `ENVIRONMENT=production`, válida 8 horas. El token va firmado con `APP_SESSION_SECRET` (HMAC-SHA256), es distinto en cada ingreso y lleva la «versión de sesión» del usuario: cerrar sesión, cambiar la contraseña o el rol, o desactivar la cuenta anula los tokens anteriores.
- **Fuerza bruta:** 5 fallos seguidos bloquean la cuenta 15 minutos (423); 20 fallos desde una misma IP en 15 minutos devuelven 429. El mensaje y el tiempo de respuesta son los mismos para usuario inexistente y contraseña incorrecta (el hash de relleno usa las mismas iteraciones). Los contadores por IP viven en memoria y se reinician con el proceso. Detrás de Caddy la IP real llega en `X-Forwarded-For`: la API no publica puertos y confía en ese encabezado con `FORWARDED_ALLOW_IPS` (`infra/production/compose.yml`) y `--proxy-headers` (`scripts/start_production.sh`); sin eso todos los visitantes compartirían la IP de Caddy y 20 fallos de cualquiera bloquearían el ingreso a todos.
- **Valores de ejemplo:** si `APP_SESSION_SECRET` o `APP_ACCESS_PASSWORD` tienen los valores de ejemplo publicados en `.env.example` o `infra/production/.env.production.example`, la aplicación responde 503 con el motivo (sin mostrar el valor) en lugar de arrancar con credenciales conocidas.
- **Reglas de administración:** nadie puede quitarse el rol de administrador ni desactivarse a sí mismo, y siempre queda al menos un administrador activo.
- **Trazabilidad:** cada ejecución guarda `executed_by` (usuario, `cli` o `github-actions`); el panel «Uso del producto» muestra ejecuciones por persona.
- **Cabeceras:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` y `Permissions-Policy`.
- Las contraseñas de Oracle se solicitan explícitamente durante el runtime y nunca se guardan en `framework_interno.db` ni en el navegador.
- **Límites:** no hay recuperación de contraseña por correo (la asigna un administrador) ni segundo factor; el bloqueo por IP no se comparte entre varias réplicas del servicio.

## Cuentas en producción (Azure)

**Recomendación: `APP_REGISTRATION_ENABLED=false` en producción.** Es el valor por defecto de `infra/production/compose.yml` y de `.env.production.example`: la opción «Solicitar acceso» desaparece del uso real y las cuentas las crea un administrador. Con `true`, cualquiera en Internet puede enviar solicitudes (quedan inactivas hasta aprobarlas, pero llenan la lista). Ábrala solo durante una demostración y vuelva a cerrarla.

**Primer administrador:** `APP_ACCESS_USERNAME` y `APP_ACCESS_PASSWORD` del `.env.production` de la VM. Se crea en el primer ingreso; después cambie su contraseña desde la aplicación («Cambiar mi contraseña»). Los valores de ejemplo publicados hacen que la aplicación responda 503.

**Crear las cuentas de Gerald y del docente** (las crea Kevin, ya como ADMIN, desde la interfaz; ninguna contraseña viaja por GitHub ni por chat):

1. Ingrese a la URL pública con el administrador.
2. Menú de su nombre (arriba a la derecha) → **Usuarios y permisos** → **Nuevo usuario**.
3. Complete nombre, usuario (p. ej. `gerald.zevallos`, `docente`) y una contraseña inicial de al menos 10 caracteres con letras y números.
4. Rol: **Administrador** para Gerald (coadministra proyectos, conexiones y cuentas); para el docente, **Tester** si solo revisará y ejecutará, o **Administrador** si debe poder ver y cambiar la configuración.
5. Entregue la contraseña inicial en persona o por un canal privado, y pida que la cambien en su primer ingreso («Cambiar mi contraseña»).
6. Si alguien olvida su contraseña: **Usuarios y permisos** → icono de llave → contraseña nueva (cierra sus sesiones).

Alternativa con el registro abierto temporalmente: ponga `APP_REGISTRATION_ENABLED=true`, recree solo la API (`docker compose ... up -d --no-deps api`), deje que cada persona use «Solicitar acceso», apruebe en **Usuarios y permisos** (cambiando el rol si corresponde) y vuelva a `false`.

## Motor de Políticas SQL (`sql_policy.py`)
El motor de validación se divide en 3 anillos de seguridad implementados con `sqlparse`:

1. **Bloqueo Global (DDL y TCL):** Rechaza de forma determinista instrucciones como `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `COMMIT`, `ROLLBACK` y PL/SQL (`BEGIN`, `DECLARE`, `EXECUTE`) para impedir la destrucción no deseada de metadatos o fugas transaccionales.
2. **Sentencias Múltiples:** Se bloquean inyecciones de múltiples consultas separadas por punto y coma `;` en todos los entornos.
3. **Control por Ambiente (`environment_type`):**
   - **`TEST`:** Permite operaciones `SELECT`, `INSERT`, `UPDATE` y `DELETE`. Cualquier sentencia DML es automáticamente encapsulada en una transacción estricta que aborta con un `ROLLBACK` obligatorio.
   - **`STAGING`:** Permite las mismas operaciones que `TEST` (con `ROLLBACK` obligatorio), pero exige **confirmación explícita desde el backend** para ejecutar cualquier operación DML; de lo contrario es rechazada.
   - **`PRODUCTION`:** Bloquea **toda sentencia DML a nivel de API backend** (independientemente del cliente). Solo permite la ejecución de sentencias `SELECT`. Además, los resultados de datos reales se enmascaran en los historiales de ejecución (`ExecutionHistory`), mostrando únicamente el número de filas operadas. Los mensajes de error originales provenientes del driver de base de datos también se enmascaran para evitar filtraciones de nombres de tablas o literales en constraints.

   > **IMPORTANTE PARA PRODUCCIÓN:** El analizador SQL del backend es una capa de defensa en profundidad, pero **no garantiza seguridad total por sí solo**. Para uso real en producción, el perfil de conexión debe configurarse obligatoriamente con un **usuario Oracle exclusivo que tenga únicamente permisos de lectura (SELECT)** sobre las tablas necesarias. Nunca utilice usuarios con permisos de escritura, DDL o roles de administrador (DBA) para los perfiles de producción.

   *Advertencia para Evaluadores*: El `executed_sql` y el `expected_result` persisten exactamente como fueron redactados en el caso de prueba. No se deben incluir PII ni datos sensibles directamente en las sentencias SQL de los tests.

## Restricción de Recursos
A fin de proteger los entornos de pruebas y producción frente a sobrecargas y errores de sintaxis que produzcan bucles, se aplican dos variables de entorno obligatorias que restringen los recursos:
- `MAX_RESULT_ROWS` (default: 1000): Protege al backend de cuellos de botella truncando las listas de datos devueltas por los comandos `SELECT`.
- `ORACLE_CALL_TIMEOUT_MS` (default: 10000 ms): Aplica un tiempo máximo de retardo por llamada para la conexión con el driver Oracle, cortando conexiones congeladas.

## Destinos de conexión (Fase 2)
- **Sin `dsn` libre.** Todas las rutas de ejecución (`/api/execute/raw`, `/quick`, `/test-case/{id}`, `/suite/{id}`) exigen un `connection_profile_id` **guardado**. Los campos `dsn`, `user` o cualquier otro desconocido se rechazan con 422; el ambiente (TEST, STAGING, PRODUCTION) siempre sale del perfil, nunca de la petición.
- **Sintaxis del destino.** `host` y `service_name` solo admiten letras, números, `.`, `-` y `_`. Así no pueden insertar partes del descriptor de conexión de Oracle (`(ADDRESS=…)`, `)(`, `=`, `/`, `@`, espacios). Se valida al crear/editar el perfil y **otra vez al ejecutar**, por si el perfil se guardó antes de existir esta regla.
- **Lista de hosts permitidos (opcional).** Si se define `ORACLE_ALLOWED_HOSTS` (por ejemplo `oracle_db,localhost`), solo esos hosts pueden usarse al crear/editar perfiles, al probar la conexión y al ejecutar. Sin la variable se permite cualquier host (uso local y académico). Para activarla en el despliegue con Docker Compose hay que añadir la variable al servicio `api`. Un perfil sigue permitiendo conectarse al host que el administrador registró: la restricción reduce el riesgo, no sustituye a un firewall ni a las cuentas de privilegios mínimos.
- **Validación por valor.** `SCALAR_VALUE` necesita leer la fila devuelta, por lo que se rechaza en PRODUCTION (las filas se ocultan).
