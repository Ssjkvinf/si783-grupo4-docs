# Tareas propuestas para Gerald

Cinco tareas pequeñas y reales que Gerald puede **implementar, probar y subir desde su propia cuenta** (rama, *pull request* y revisión de Kevin). Son una propuesta: nadie las ha hecho ni se ha simulado su trabajo. Solo cuenta como contribución lo que aparezca en el historial de Git con su autoría.

Contexto: hasta el 06‑oct‑2026 el historial del repositorio tiene 35 commits de una sola persona; la rúbrica pide 40–60 % por integrante, así que conviene repartir trabajo **con evidencia** (commits y PR de cada uno).

Preparación común: clonar, `python -m venv venv`, instalar `requirements.txt`, comprobar `python -m pytest -q` y leer `docs/estandar-programacion.md`.

| # | Tarea | Archivos | Cómo se prueba | Hecho cuando | Tamaño [estimación] |
| --- | --- | --- | --- | --- | --- |
| T1 | **Linter en CI.** Añadir `ruff` (configuración mínima) y un paso en `.github/workflows/tests.yml`; corregir lo que marque en `app/` y `scripts/` sin cambiar el comportamiento. | `ruff.toml` o `pyproject.toml`, `tests.yml`, archivos de `app/` | `ruff check app scripts` sin errores; `python -m pytest -q` igual que antes | PR con el paso de CI y el resultado de la suite antes/después | 2–4 h |
| T2 | **Docstrings que faltan.** `docs/generated/cobertura-docstrings.md` lista los vacíos: hoy 3 módulos, 30 clases, 29 funciones y 19 métodos públicos sin docstring (y 5 endpoints con la descripción vacía en `docs/generated/api-endpoints.md`: `POST /api/login`, `POST /api/logout`, `GET /health`, `GET /api/excel/cases/export`, `GET /api/excel/results/export`). Empezar por esos 5 y por `app/engine/validator.py`, y añadir una prueba que falle si una operación no tiene descripción. | `app/main.py`, `app/api/excel.py`, `app/engine/validator.py`, `tests/test_phase5_docs.py` (o un archivo nuevo) | `python scripts/docs/gen_docs.py` y `python -m pytest -q tests/test_phase5_docs.py`; la cobertura de la tabla sube | Los 5 endpoints con descripción, prueba añadida y documentación regenerada en el mismo PR | 2–4 h |
| T3 | **Segunda suite de reglas de demostración** (por ejemplo «sin espacios al inicio o final en `NAME`», «sin nombres repetidos»), **sin tocar** las 5 reglas existentes ni los conteos de las pruebas actuales. Sumarla en `demo_scenario.py` con su prueba. | `app/services/demo_scenario.py`, `tests/test_phase2_scalar_demo_targets.py` | Pruebas con Oracle simulado; **además**, si Gerald tiene Docker, con el Oracle desechable (`docs/demostracion-fase2.md` §3–§4), anotando el resultado real | Suite creada de forma idempotente, prueba pasando y resultado Oracle real **solo si** se ejecutó | 3–5 h |
| T4 | **Medir la usabilidad (OS‑1/OS‑2).** Dirigir las sesiones con 3–5 compañeros según `docs/protocolo-usabilidad.md`, llenar la hoja de registro y resumir (tiempos, ayudas, comprensión). Es trabajo de campo, no de código. | `docs/protocolo-usabilidad.md` (hoja) y un nuevo `docs/resultados-usabilidad.md` | Los registros crudos de cada sesión | Tabla con datos reales o una nota honesta de que no se pudo medir | 1 día |
| T5 | **Ejecutar en GitHub lo ya preparado y guardar evidencia.** Tras el *push* de Kevin: ejecutar `Comprobaciones SQL (CLI + Excel)` (con y sin dato inválido), `Documentación (generar)` y `Documentación técnica (Pages)` en modo construcción; capturar resumen y artefactos; registrar lo que falle. | Ninguno (evidencia en un issue o en `docs/`) | Ejecuciones reales de Actions | Capturas con nombre (ver informe de la Fase 5) y lista de fallos corregidos o abiertos | 3–5 h (más correcciones) |

## Reglas para que cuente como suyo

1. Rama propia (`feature/…`, `fix/…`, `docs/…`) y PR hacia `main`; Kevin revisa y viceversa.
2. Commits con su cuenta y su nombre (`git config user.name` / `user.email` propios); sin reescribir historial.
3. El PR dice qué se probó y con qué resultado real; si algo no se ejecutó, lo dice.
4. Nada de secretos en el PR.

## Tareas adicionales (también para Gerald, desde su cuenta)

| # | Tarea | Archivos exactos | Criterio de aceptación | Tamaño [estimación] |
| --- | --- | --- | --- | --- |
| T6 | **Regenerar FD01–FD05 en Word y PDF** con las fuentes de `docs/informes/` sobre la plantilla del curso (borrar el control de versiones de ejemplo «MPV/ELV/ARV 10/10/2020»; autores KHC y GZP). Exportar los diagramas a imagen desde `docs/diagramas/*.mermaid` | Los `.docx`/`.pdf` en la carpeta que acuerden (p. ej. `entregables/`) y, si cambia el texto, la fuente `docs/informes/*.md` | La búsqueda de `SUNAT`, `reactivo`, `laboratorio`, `obra`, `residente`, `almacenero`, `partida`, `proveedor`, `entrevista`, `encuesta`, `observación directa` no da resultados fuera de citas; índices y numeración coinciden con el cuerpo | 1–1,5 días |
| T7 | **Evidencia del despliegue (OS‑7):** abrir la URL pública desde **otra red**, iniciar sesión, ejecutar un caso y guardar capturas. Si no abre, anotar el síntoma tal cual | `docs/evidencia-despliegue.md` (nuevo) y las capturas | Fecha, red usada, resultado real (éxito o fallo) y capturas; sin contraseñas visibles | 1–2 h |
| T8 | **Revisar el pull request de Kevin** (revisión cruzada): leer `git diff`, probar `python -m pytest -q` y `python scripts/docs/gen_docs.py --check`, dejar comentarios en el PR | Ninguno (comentarios y aprobación en GitHub) | Al menos 3 comentarios concretos o una aprobación con la lista de lo que probó | 2–3 h |

## Reparto realista y cómo preguntarlo

- **Hechos:** hasta el 06‑oct‑2026 hay 35 commits, todos de Kevin, y esta entrega añade 6 más suyos. Con commits o líneas como medida, un 40–60 % de Gerald **no es alcanzable** en el tiempo que queda sin artificios (partir commits o reescribir historial), y no se debe hacer.
- **Lo que sí es honesto:** que Gerald sea dueño de flujos de trabajo completos, con sus propios commits y *pull requests*: T1–T3 (código y pruebas), T4 (medición con personas), T5 y T7 (evidencia en GitHub y Azure), T6 (documentos finales) y T8 (revisión). Suman unas 35–40 h [estimación], frente a unas 20 h [estimación] que le quedan a Kevin (configurar GitHub, corregir lo que fallen las primeras ejecuciones, presentación, reversión del despliegue y Python 3.12).
- **No sabemos cómo mide el docente** (commits, líneas, pull requests y revisiones, participación en la presentación). Pregúntenlo antes de repartir. Texto sugerido: «Ingeniero, para el criterio de contribuciones (40–60 % por integrante): ¿se mide por commits del historial de GitHub, por líneas, por pull requests y revisiones, o por participación en el trabajo y la presentación? Nuestro historial inicial tiene los commits de uno de nosotros; queremos repartir el trabajo restante y dejarlo documentado con PR y revisiones de cada uno. ¿Considera también issues y revisiones?».
- Cada tarea se sube con commits y PR propios; no se cuentan tareas que no estén en el historial.
