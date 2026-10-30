# Título, problema y objetivos (versión corregida — Fases 1 y 5)

> Fuente editable para actualizar la Propuesta del Proyecto (FD06; ver nota en `informes/LEEME.md`: la consigna de la Unidad II lista FD01–FD05, y FD06 es el documento donde ya figuraban título, problema y objetivos) y alinear FD01–FD04. Todo se contrastó con el código del repositorio y con las fuentes citadas.
> Convención: **[Hecho]** comprobado en el repositorio (archivo, prueba o ejecución indicada) · **[Fuente]** respaldado por un documento externo que se abrió y leyó · **[Meta]** objetivo aún por comprobar · **[Hipótesis]** supuesto sin medición · **[Futuro]** no implementado.

## 1. Título propuesto

**«Aplicación web para repetir comprobaciones SQL sobre Oracle y conservar su evidencia de ejecución. Tacna, 2026»**

Motivo: «Framework de pruebas de base de datos SQL» es genérico y promete más de lo que el producto hace. El título nuevo nombra el problema (repetir comprobaciones), el motor (Oracle) y el resultado (evidencia).

## 2. Problemática

### 2.1 Necesidad potencial (no observada en una empresa)

Quien modifica una consulta o una operación sobre los datos de Oracle debe comprobar que sigue dando lo esperado. Si la comprobación queda como una ejecución aislada, después cuesta repetirla, compararla con la anterior y demostrar qué se ejecutó y con qué resultado. El problema que se atiende es **reunir en un lugar la sentencia, la conexión, el resultado esperado y el registro de cada ejecución**.

**Es una necesidad potencial planteada por el equipo.** No hubo entrevistas, observación en una organización, cronometraje ni medición de ahorro (FD01 §2 y §8, FD02, FD06 §1). La idea surgió de una lista de proyectos propuesta en el curso.

### 2.2 Antecedentes (fuentes abiertas y leídas)

Las URL de FD06 se abrieron el 20‑oct‑2026. Esto es lo que respaldan y lo que no.

| Fuente | Lo que se verificó en el documento | Lo que **no** respalda |
| --- | --- | --- |
| Contraloría General de la República (2024), TdR de mejora de software de microformas digitales | Verificado en el PDF: **Anexo 04.1** (procedimiento de pruebas funcionales, con casos de prueba y ambientes de pruebas con «instancia de base de datos»), **Anexo 04.2** (documento de plan de pruebas, que lista «pruebas de datos e integridad de Base de Datos») y **Anexo 04.3** (informe de pruebas, con «evidencias» y resultado de cada caso). La cita «anexos 4.1 a 4.3» de FD06 es **correcta**. | Que la entidad tenga el problema descrito ni que use este producto. |
| Ministerio del Ambiente (s. f.), TdR de la plataforma Huella de Carbono Perú | Verificado: apartado **V (Entregables)** incluye un «Documento de Pruebas de Base de Datos, revisado y aprobado por el Administrador de Base de Datos»; el apartado IV (Actividades) prevé la ejecución de pruebas de base de datos; el **Anexo 1** indica **Oracle 11g**. | Lo mismo. **Límite del producto:** este producto **no** sirve para esa entidad tal como está: usa python-oracledb en modo Thin (Oracle 12.1 o posterior) y nunca activa el modo Thick. La documentación del controlador dice que con el modo Thick y un cliente Oracle 19 se puede conectar a Oracle 11.2 o posterior, **pero** desde la versión 4.0.0 solo prueba el modo Thick con bases 19 a 26 (11.2 sin pruebas documentadas). **No verificado por nosotros** (ni se implementó ni se probó el modo Thick). |
| Oracle, *About DML statements and transactions* (23ai) | Los cambios sin confirmar se pueden deshacer con `ROLLBACK`; Oracle emite un `COMMIT` implícito antes y después de cualquier sentencia DDL. | Que el programa garantice reversibilidad en cualquier base: no cubre secuencias, transacciones autónomas ni efectos fuera de la transacción. |
| Oracle, *SQL Developer: Unit testing* | SQL Developer ya agrupa pruebas en **suites**, las ejecuta sobre una conexión, guarda y reporta resultados, y tiene **línea de comandos** (`sdcli`). Por eso no se afirma que este producto sea el primero ni que sea mejor. | Superioridad frente a SQL Developer. |
| sqlparse, *Introduction* | El analizador es «intencionalmente no validador». Por eso las reglas del programa se acompañan de cuentas Oracle de privilegio mínimo. | — |
| Presidencia del Consejo de Ministros, guías de servicios digitales | Recomiendan probar con usuarios (no se reabrió en esta fase). | — |

### 2.3 Pregunta del proyecto

¿Cómo puede una aplicación web ayudar a una persona a ejecutar una comprobación SQL sobre Oracle, entender si coincide con lo esperado y conservar la evidencia para repetirla, **sin exigirle configurar varios módulos antes de ver un primer resultado**?

### 2.4 Para quién

Personas que desarrollan o prueban sobre Oracle (desarrollo, QA) y quienes autorizan las conexiones (DBA). **No existe empresa cliente** [Hecho: FD01, FD02, FD06].

### 2.5 Qué significa un resultado y qué no

- **PASS** significa que la consulta dio lo que la regla configurada esperaba. **No** significa que toda la base sea correcta: solo comprueba lo que la regla dice (ver FD01 §10.1).
- **FAIL**: se ejecutó, pero no coincide. **ERROR**: no se pudo ejecutar o evaluar (SQL inválido, tabla inexistente, contraseña, conexión, o rechazo por política).
- **Bloquear `DROP`/DDL es un control de seguridad, no el beneficio principal.** El beneficio buscado es repetir y documentar comprobaciones. El bloqueo existe porque Oracle confirma el DDL por sí solo (Oracle, 23ai) y porque el análisis léxico no basta: hace falta además una cuenta de privilegio mínimo.

## 3. Alcance en tres capas

| Capa | Contenido | Estado |
| --- | --- | --- |
| **Implementado** (verificable en el repositorio) | Proyectos, perfiles de conexión sin contraseña, casos (`ROW_COUNT`, `SCALAR_VALUE`, `EXISTS`) con **comparación automática**, suites, historial con «ejecutado por», política de SQL por ambiente, prueba rápida en «Inicio», asistente de reglas, demostración guiada, **Analizar una tabla** (reglas propuestas desde el diccionario de datos y el estado actual de los datos), **comparación con la ejecución anterior**, reporte descargable por corrida, dashboard de uso (también por persona y origen), **usuarios con roles ADMIN/TESTER** y solicitud de cuenta con aprobación, Excel (plantilla/importar/exportar), CLI con códigos de salida, base interna SQLite con Alembic. | [Hecho] ver `docs/informes/FD05-informe-final.md` §6 |
| **Demostración académica** | Escenario sobre `FRAMEWORK_TEST_ITEMS` en un Oracle Free local desechable; suites de reglas y de ejemplos de FAIL/ERROR; Terraform, copias, release y workflows **preparados**. La VM de Azure se menciona en los documentos pero **no se verificó**. | Parcial: ver estados «local / Oracle real / GitHub / Azure» en FD05 §6.2 |
| **Trabajo futuro** | Recuperación de contraseña por correo y segundo factor; permisos por proyecto; historial no editable (auditoría inmutable); otros motores; Oracle 11g; carga y rendimiento; integración con Jira/IDE; ahorro medido con un cliente. | [Futuro] |

## 4. Objetivos

### 4.1 Objetivos de investigación (documentales)

| ID | Objetivo | Cómo se comprueba | Estado |
| --- | --- | --- | --- |
| OI‑1 | Determinar con la documentación de Oracle qué sentencias se pueden revertir y cuáles confirman solas. | Tabla sentencia → ¿reversible? → ¿qué hace la política? | **Hecho**: FD05 anexo A (derivada de `app/security/sql_policy.py` y probada en `tests/test_engine.py`, `tests/test_environment_policies.py` y, con Oracle desechable, `tests/test_oracle_phase2.py`). |
| OI‑2 | Identificar qué debe conservar un caso para poder repetirlo. | Cada columna de `test_cases` y `execution_history` trazada a un requisito. | **Hecho**: `docs/generated/diccionario-datos.md` describe el 100 % de las columnas (el generador falla si falta una) y FD05 anexo B las traza a RF. |
| OI‑3 | Revisar una herramienta existente y precisar el alcance propio. | Tabla comparativa con ≥ 5 criterios, sin afirmar superioridad. | **Hecho (documental)**: FD05 §3.4, basada en la página de SQL Developer leída; sin pruebas de uso comparadas. |

### 4.2 Objetivos de la solución (metas medibles)

Los umbrales de OS‑1 y OS‑2 son **propuestas del equipo**; no hay medición.

| ID | Meta | Medida y umbral | Cómo se comprueba | Estado hoy |
| --- | --- | --- | --- | --- |
| OS‑1 | Primer resultado rápido | Tiempo de «abrir la aplicación» a «ver PASS/FAIL/ERROR» ≤ 5 min y sin ayuda en ≥ 4 de 5 participantes | `protocolo-usabilidad.md` con 3–5 compañeros, antes y después | **[Meta] sin medir** |
| OS‑2 | Comprender el resultado | ≥ 80 % explica qué se esperaba y qué se obtuvo | Misma sesión | **[Meta] sin medir** |
| OS‑3 | Resultados correctos y distinguibles | 100 % de los escenarios dan el estado documentado (PASS/FAIL en `ROW_COUNT`, `SCALAR_VALUE`, `EXISTS`; tabla inexistente → ERROR) | Pruebas contra Oracle desechable | **Verificado con Oracle real local**: 18‑oct‑2026 (Fase 2: 23 pruebas Oracle, suite 198 passed) y **26‑oct‑2026** tras usuarios, análisis y comparación (28 pruebas Oracle; suite completa 490 passed, 0 omitidas; Oracle Free desechable en Docker local). No repetido tras las correcciones del 28‑oct‑2026 (Docker apagado ese día). |
| OS‑4 | Control de cambios | Filas antes = después tras `INSERT`, medido con conexión independiente; tabla intacta tras intento de `DROP`, con cuenta de privilegios mínimos | Pruebas Oracle desechable | **Verificado con Oracle real local (Fase 2)**, mismo alcance y salvedad. Límite: secuencias y transacciones autónomas no se revierten. |
| OS‑5 | Evidencia conservada | 100 % de las ejecuciones producen un registro con SQL, esperado, obtenido, estado, fecha, duración y ambiente | `tests/test_quick_execution.py`, `tests/test_api.py` (simulados) y suite de Oracle (15 registros) | **Verificado** (simulado y Oracle real local) |
| OS‑6 | Repetir y revisar | Caso ejecutado ≥ 2 veces → ≥ 2 registros ordenados por fecha | Suite repetida en la prueba Oracle (3 ejecuciones) | **Verificado** (Oracle real local) |
| OS‑7 | Acceso desplegado | Abrir por HTTPS desde otra red, iniciar sesión y ejecutar un caso | Prueba manual con capturas | **No verificado** (Azure no se consultó) |
| OS‑8 | Integraciones | CLI devuelve 0/1/2 según PASS/FAIL/ERROR; Excel importa con validación y exporta resultados | `tests/test_phase4_cli.py`, `tests/test_phase4_excel.py` | **Verificado en local** con un sustituto SQLite de Oracle; el workflow de GitHub **nunca se ejecutó** |
| OS‑9 | Dashboard de uso | Cifras calculadas desde datos guardados, con definición de cada métrica y estado vacío; uso por persona y por origen | `tests/test_phase4_usage.py`, `tests/test_usuarios.py` | **Verificado en local** (reloj fijo); sin datos reales de uso |
| OS‑10 | Acceso por persona y rol | Sin sesión: 401; TESTER: 403 en usuarios, proyectos y conexiones; contraseñas solo como hash; bloqueo tras 5 fallos | `tests/test_usuarios.py`, `tests/test_auth.py` y matriz de permisos de las 52 operaciones de la API | **Verificado en local** (28‑oct‑2026) y en la imagen Docker con Oracle real (26‑oct‑2026) |
| OS‑11 | Reglas sin escribir SQL | Analizar una tabla propone reglas que dan PASS sobre los mismos datos y FAIL al romper uno | `tests/test_analisis_tabla.py` (sustituto SQLite) y `tests/test_oracle_fase_c.py` (Oracle real) | **Verificado** (local y Oracle real local, 26‑oct‑2026) |

### 4.3 Hipótesis de utilidad (no medidas)

- H1: una persona nueva llega al primer resultado más rápido con «Inicio» que con el flujo por módulos.
- H2: repetir una suite es más rápido que repetir las consultas a mano. FD01 modela 5, 8 y 12 min por repetición como **escenarios**; ninguno se midió.
- H3: el historial reduce el tiempo de revisar un fallo.

Hasta ejecutar `protocolo-usabilidad.md` y un cronometraje comparado, **ninguna cifra de ahorro es un resultado**.

## 5. Lo que este documento no afirma

- No hay entrevistas, encuestas, empresa cliente, cronometrajes ni porcentaje de ahorro.
- VAN, S/ 8 000 anuales, 8 minutos, S/ 4 500 de implantación, etc. (FD01) son **escenarios de planificación**.
- No hay compatibilidad con otros motores ni con Oracle anterior a 12.1 (el modo Thick y un cliente Oracle 19 podrían alcanzar la 11.2 según la documentación del controlador; **no verificado**, no implementado); no hay certificación de seguridad.
- La URL en Azure figura en documentos; no se verificó.
- No hay usuarios reales de la aplicación más allá del equipo: las cuentas Administrador/Tester se probaron con datos ficticios.

## 6. Dónde actualizar los demás documentos

Ver `docs/informes/matriz-afirmaciones.md` (afirmación por afirmación) y las fuentes editables en `docs/informes/`.
