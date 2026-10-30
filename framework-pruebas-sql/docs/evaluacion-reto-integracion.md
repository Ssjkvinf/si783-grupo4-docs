# Evaluación del reto de integración

**Decisión que corresponde a Kevin y Gerald.** Este documento evalúa y recomienda; no implementa nada nuevo.

## 1. Qué pide la consigna

Texto del encargo (el original de la consigna **no se encontró como archivo**; ver `docs/informes/LEEME.md`): «integrar 3 herramientas externas (GitHub, Office, Jira, módulo de IDE, CLI, etc.) o integrar con VS Code mediante extensión, skill o agente». La rúbrica de 20 puntos que se conoce **no tiene una fila propia para el reto**: conviene preguntar al docente si puntúa y cómo.

## 2. Evaluación honesta de lo que existe

Criterio aplicado: una integración cuenta si **el producto hace algo útil con la herramienta y se puede demostrar**; un archivo generado o un enlace solos no cuentan.

| Integración | Qué hace de verdad (verificable) | ¿Cumple la redacción? | Debilidades |
| --- | --- | --- | --- |
| **CLI** (`python -m app.cli`) | Importa/exporta Excel, ejecuta casos o una suite contra Oracle y devuelve 0/1/2/3/4; escribe Markdown, JUnit y JSON; contraseña solo por variable de entorno. 19 pruebas, incluida ejecución como subproceso. | **Sí, literalmente**: «CLI» figura en la lista. | Es un cliente del propio producto; un docente puede decir que no integra nada externo. Probada con un sustituto SQLite de Oracle, **no con Oracle real**. |
| **GitHub Actions** (`.github/workflows/sql-checks.yml`) | Levanta un Oracle desechable, aplica Liquibase, importa un Excel de reglas, ejecuta la CLI, publica resumen y artefactos y falla con el código de la CLI. | **Sí, en la redacción** («GitHub»), **si se ejecuta**. | **Nunca se ejecutó en GitHub**: solo hay análisis estático. El producto no llama a la API de GitHub; es el workflow el que usa al producto (es integración con CI, no con GitHub como servicio). |
| **Excel** (`app/services/excel_io.py`) | Plantilla con lista desplegable, importación todo-o-nada con validación (SQL, fórmulas, tamaño, duplicados), exportación de casos y de resultados con colores. 33 pruebas con openpyxl real. | **Sí en la redacción** («Office»). | Es integración por formato de archivo (no usa Excel ni Microsoft 365). No se abrió en Excel real en esta fase. |

Veredicto: **por la lista literal, GitHub + Office + CLI son tres herramientas nombradas.** La profundidad es desigual: Excel y la CLI están probadas en local; GitHub Actions está sin demostrar. Si el docente interpreta «externa» de forma estricta, la CLI es la más cuestionable.

## 3. Opciones

Esfuerzos son **estimaciones**, no mediciones.

| Opción | Qué se hace | Pros | Contras | Esfuerzo | Costo |
| --- | --- | --- | --- | --- | --- |
| **A. Mantener GitHub + Excel + CLI y demostrarlas** | Subir los cambios, ejecutar `SQL checks` a mano (con y sin `provocar_dato_invalido`), guardar resumen, artefacto y captura del fallo; abrir el Excel de resultados en Excel real | Cubre la lista literal; ya está construido; solo falta ejecutarlo | La CLI es débil como «externa»; depende de que el Actions funcione a la primera | 0,5 día | 0 |
| **B. A + Jira o webhook** (una suite en FAIL crea una incidencia o un mensaje con el enlace al informe) | Paso opcional del workflow que llama a la API de Jira o a un webhook (Teams/Discord/Slack) con un secreto | Una herramienta claramente externa; mejora el relato («falla → ticket») | Necesita un sitio Jira gratuito y un token (secreto); webhook es más barato pero más débil; más superficie de error | 1,5–3 días | 0 (plan gratuito) |
| **C. Extensión de VS Code** | Extensión que lista casos, ejecuta la CLI y muestra resultados | Cumple la segunda alternativa de la consigna | Es lo más caro; riesgo de quedar a medias | 3–5 días | 0 |
| **D. Skill o tareas de VS Code** | `.vscode/tasks.json` que ejecuta `run`/`import-excel` y una *skill* (instrucciones para un agente) que explica cómo ejecutar comprobaciones con la CLI | Barato; cubre «skill» | Puede juzgarse superficial si no hay demostración real con el agente | 0,5–1 día | 0 |

## 4. Recomendación

**Opción A como base, y B solo si queda tiempo.** Es la más sólida por costo: el 80 % del trabajo ya existe y lo que falta es **ejecutarlo en GitHub y mostrarlo**. Sin esa ejecución, ninguna opción es defendible. Orden sugerido:

1. Subir los cambios (Kevin) y ejecutar `SQL checks` en GitHub; guardar el artefacto `reporte-sql-checks`.
2. Demostrar el flujo «dato inválido → FAIL → código de salida ≠ 0 → informe» con `provocar_dato_invalido`.
3. Preguntar al docente si la CLI cuenta como herramienta externa y si el reto puntúa.
4. Si la respuesta es no a la CLI: añadir B con un webhook (≈ 1,5 días) antes que C.

No se implementó nada de esto en la Fase 5: ninguna opción es trivial (todas requieren decisiones, secretos o ejecución en GitHub).
