# Manual de Usuario

La aplicación permite **comprobar consultas SQL sobre Oracle**: usted dice qué espera que devuelva una consulta, la aplicación la ejecuta, compara y guarda la evidencia (consulta, esperado, obtenido, estado, fecha, duración y quién la ejecutó). Cada comprobación termina en:

- **PASS**: coincide con lo esperado.
- **FAIL**: se ejecutó, pero no coincide (posible problema en los datos).
- **ERROR**: no se pudo ejecutar o evaluar (tabla inexistente, contraseña, sentencia no permitida…).

Un PASS significa que **la regla configurada** se cumple, no que toda la base esté correcta.

## 1. Ingreso y cuentas

Si el control de acceso está activado (`APP_ACCESS_ENABLED=true`), se abre la pantalla de ingreso.

- **Ingresar**: usuario y contraseña. Tras 5 intentos fallidos seguidos la cuenta se bloquea 15 minutos; tras 20 fallos desde un mismo equipo en 15 minutos, ese equipo debe esperar.
- **Solicitar acceso**: nombre, usuario y contraseña (al menos 10 caracteres, con letras y números, sin incluir el usuario). La cuenta queda **pendiente** hasta que un administrador la aprueba. El administrador puede desactivar esta opción (`APP_REGISTRATION_ENABLED=false`).
- **Sesión**: dura 8 horas. «Salir» (menú de su nombre, arriba a la derecha) la cierra en todos los equipos.
- **Cambiar mi contraseña**: en el mismo menú. Cierra sus otras sesiones.

### Roles

| Puede… | Tester | Administrador |
| --- | --- | --- |
| Usar Inicio, el asistente de reglas, Analizar una tabla y la demostración guiada | Sí | Sí |
| Crear, ejecutar y eliminar casos y suites; importar o exportar Excel | Sí | Sí |
| Ver el historial, los reportes y el panel «Uso del producto» | Sí | Sí |
| Probar una conexión existente | Sí | Sí |
| Crear, editar o eliminar proyectos y conexiones Oracle | No | Sí |
| Aprobar solicitudes, cambiar roles, asignar contraseñas, eliminar cuentas | No | Sí |

El primer administrador lo crea el servidor con `APP_ACCESS_USERNAME` y `APP_ACCESS_PASSWORD` (ver `docs/seguridad.md`). La interfaz oculta lo que un Tester no puede hacer, pero quien decide es el servidor (responde 403).

## 2. Primera comprobación («Inicio»)

1. **Conectar**: elija una conexión Oracle del proyecto activo y escriba la contraseña del usuario Oracle. Solo se usa para esa ejecución; **no se guarda**.
2. **Elegir qué comprobar**:
   - con el **asistente de reglas** (sin escribir SQL): «la tabla no está vacía», «ninguna fila con la columna vacía», «sin valores repetidos», «la columna solo contiene ciertos valores», etc.; o
   - escribiendo un `SELECT`.
3. **Decir qué espera**: un número, sí/no o un valor. Con la opción **Automático (recomendado)** la aplicación decide cómo comparar y lo explica:
   - si la consulta calcula un único valor (`COUNT`, `SUM`, `AVG`, `MIN`, `MAX`) compara ese valor;
   - si escribe un número y la consulta no calcula un valor, compara la cantidad de filas;
   - si escribe sí/no, comprueba si devuelve filas;
   - si escribe un texto, compara el valor devuelto.
   Puede elegir la comparación a mano si lo prefiere.
4. **Ejecutar**: verá PASS, FAIL o ERROR con «lo que se esperaba», «lo que se obtuvo» y «por qué». Después puede **Repetir**, **Guardar como caso** (confirmando el valor esperado) o **Ver en el historial**.

En Inicio solo se ejecutan `SELECT`. Para `INSERT`, `UPDATE` o `DELETE` use Casos y Suites.

**Demostración guiada**: con una conexión de ambiente TEST, ejecuta en menos de un minuto reglas que pasan, un FAIL y un ERROR de ejemplo, un `INSERT` que se revierte y un `DROP` que se rechaza.

## 3. Analizar una tabla

Menú **Analizar una tabla**: elija una conexión TEST o STAGING, escriba la contraseña y el nombre de la tabla (`TABLA` o `ESQUEMA.TABLA`).

La aplicación lee la estructura (clave primaria, columnas obligatorias) y cómo están hoy los datos (vacíos, valores distintos, valores posibles, mínimo y máximo) con **solo consultas SELECT**, y propone reglas. Las marcadas como «recomendadas» vienen seleccionadas. Elija las que quiera y pulse **Guardar** o **Guardar y ejecutar**: se crea una suite con un caso por regla.

Las reglas propuestas describen cómo están los datos **hoy**: sirven para avisar cuando algo cambia, no prueban que hoy estén bien. No está disponible en PRODUCTION (allí las filas se ocultan).

## 4. Proyectos y conexiones (administrador)

- **Proyectos**: agrupan conexiones, casos, suites e historial. El selector «Proyecto activo» (arriba) define dónde trabaja.
- **Conexiones Oracle**: nombre, servidor (host), puerto (1521 por defecto), servicio (p. ej. `FREEPDB1`), usuario Oracle y ambiente. Opcionalmente escriba la contraseña para **probar al guardar**; no se guarda.
- **Ambientes**:
  - `TEST`: `SELECT` y cambios (`INSERT`, `UPDATE`, `DELETE`) que siempre se revierten con `ROLLBACK`.
  - `STAGING`: igual que TEST, pero pide confirmación antes de ejecutar cambios.
  - `PRODUCTION`: solo `SELECT`; no se muestran las filas, solo su cantidad. Use un usuario Oracle de solo lectura.
- `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT` y bloques PL/SQL se rechazan **antes** de llegar a Oracle. El rollback no deshace secuencias (`NEXTVAL`) ni lo que haga una transacción autónoma.

## 5. Casos y suites

- **Casos de prueba**: nombre, consulta, cómo comparar (Automático, cantidad de filas, valor o existe sí/no) y resultado esperado. También se crean desde Inicio, desde «Analizar una tabla» o importando un Excel (plantilla descargable; se valida antes de guardar).
- **Suites**: grupos de casos que se ejecutan juntos. Cada tarjeta muestra las barras de las últimas corridas (verde: todo pasó; ámbar o rojo: hubo fallos) y un enlace al reporte de la última.
- **Ejecutar**: elija la conexión y escriba la contraseña. En STAGING y PRODUCTION se pide confirmación.
- **Comparación con la vez anterior**: el resultado de una suite marca cada caso como «Igual que la vez anterior», **«Antes pasaba y ahora no»** (fallo nuevo), «Antes fallaba y ahora pasa» o «Primera ejecución».
- **Descargas**: «Descargar reporte» (página HTML que se puede imprimir o guardar como PDF) y «Excel de esta corrida».

Un caso, una suite o una conexión que ya tienen ejecuciones en el historial no se pueden eliminar: así se conserva la evidencia.

## 6. Historial

Lista las ejecuciones del proyecto activo con fecha, qué se ejecutó (caso y suite por nombre), resultado, esperado y obtenido, duración y **quién** la lanzó. Filtros: resultado, suite, caso y usuario. El detalle muestra la consulta, la conexión, el origen (Interfaz, Inicio, CLI o GitHub Actions), el rollback y la comparación con la ejecución anterior del mismo caso, y permite descargar el reporte de su corrida.

## 7. Uso del producto

Panel con cifras calculadas desde los datos guardados: ejecuciones por día, PASS/FAIL/ERROR, casos y suites más usados, origen de las ejecuciones, **ejecuciones por persona** y otras acciones (Excel, demostración, análisis de tablas). Cada cifra tiene su definición y sus límites (por ejemplo, las ejecuciones anteriores a las cuentas individuales aparecen como «sin usuario»).

## 8. Ayuda

La sección **Ayuda** resume los tres pasos, explica PASS/FAIL/ERROR y los roles, qué protege la aplicación y preguntas frecuentes.
