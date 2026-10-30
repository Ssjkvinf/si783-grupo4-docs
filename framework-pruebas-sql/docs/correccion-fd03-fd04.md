# Propuesta de corrección de FD03 (SRS) y FD04 (SAD)

**Estado: PROPUESTA. Los PDF no se han modificado.**

En el repositorio solo existen `FD03_Informe_SRS_FrameworkSQL.pdf` y `FD04_Informe_SAD_FrameworkSQL.pdf`. Los `.docx` y `.md` editables fueron eliminados el 06‑oct‑2026 (commits `59b1e8e` y `50f2b85`); en el historial solo figuran los `.docx` del commit inicial del repositorio (`bfeac77`), presumiblemente las plantillas del curso; no se abrieron y no hay garantía de que equivalgan al contenido actual de los PDF. Por eso este documento lista qué corregir y con qué texto, pero la corrección real exige la fuente editable (ver §3).

Las páginas son las de la numeración del PDF (conteo de páginas físicas). FD01 §11 ya reconoce estos desajustes.

## 1. Frases ajenas al proyecto

### FD03 — Especificación de requerimientos

| Pág. | Texto encontrado (resumen) | Por qué no corresponde | Texto propuesto |
| --- | --- | --- | --- |
| 5 (índice p. 3) | «I. Generalidades de la Empresa» con la UPT como «Nombre de la Empresa», visión y misión; «4. Organigrama» | No hay empresa: es un proyecto académico (FD01, FD02, FD06). | «I. Contexto académico del proyecto»: curso, docente, integrantes, origen (proyecto elegido entre los propuestos en el curso) y declaración «no existe organización cliente». Eliminar organigrama. |
| 6 | Objetivo de negocio: «cumplimiento de regulaciones exigidas por entidades fiscalizadoras como la SUNAT» | Texto de otro proyecto. | «Facilitar que una persona repita comprobaciones SQL sobre Oracle y conserve la evidencia de cada ejecución.» |
| 6 | «materiales y reactivos necesarios estén siempre accesibles … prácticas de laboratorio» | Texto de otro proyecto. | «Reducir el esfuerzo de repetir y comparar comprobaciones SQL.» (como meta, sin cifra) |
| 6 | «ambiente de trabajo organizado y seguro para docentes e investigadores … insumos de laboratorio» | Texto de otro proyecto. | «Aplicar reglas distintas según el ambiente de conexión (TEST, STAGING, PRODUCTION).» |
| 6 | «modernización de la gestión académica mediante la optimización de procesos administrativos» | No es el alcance del producto. | Retirar. |
| 7–8 | «Viabilidad técnica: El laboratorio cuenta con equipos … Intel Core i5 12.ª gen, 12 GB RAM, SSD 256 GB … Windows» | Describe equipos de un laboratorio, no el producto (corre en un servidor y se usa con un navegador). | Resumir la viabilidad técnica con lo comprobable: Python/FastAPI, SQLite interna, Oracle como base objetivo, navegador; remitir a FD01 §5 para el despliegue. |
| 9 (índice p. 3) | «5. Información obtenida del Levantamiento de Información … entrevistas, encuestas, observación directa» | **No se hicieron** (FD01 §11; FD06 §1). Es una afirmación falsa. | Reemplazar por «Fuentes consultadas», con los antecedentes de FD06 y la frase: «No se realizaron entrevistas, encuestas ni observación en una organización.» |
| 9 | «proceso propuesto para estandarizar la gestión de reactivos» | Texto de otro proyecto. | «… para repetir comprobaciones SQL y conservar su evidencia.» |
| 35 | «datos persistentes, como los reactivos, materiales y usuarios» | Entidades inexistentes; además no hay tabla de usuarios (acceso con credencial única). | «… como proyectos, perfiles de conexión, casos de prueba, suites e historial de ejecuciones.» |

### FD04 — Arquitectura de software

| Pág. | Texto encontrado | Por qué no corresponde | Texto propuesto |
| --- | --- | --- | --- |
| 27 | CU02 «Gestionar proyecto»: «permite al administrador crear un usuario nuevo» | No hay gestión de usuarios. | «Permite crear, editar, listar y eliminar proyectos (con restricción si tienen dependencias) y elegir el proyecto activo.» |
| 27 | CU03 «Gestionar perfil Oracle»: «gestionar las obras» | Texto de otro proyecto. | «Permite registrar, editar y eliminar perfiles de conexión Oracle sin guardar la contraseña, y probar la conexión.» |
| 27 | CU04 «Gestionar caso de prueba»: «registrar una partida nueva» | Texto de otro proyecto. | «Permite crear, editar y eliminar casos con SQL, tipo de validación (`ROW_COUNT` o `EXISTS`) y resultado esperado.» |
| 28 | CU05 «Gestionar suite»: «el residente de obra registrar el avance físico» | Actor y acción ajenos. | «Permite agrupar casos del mismo proyecto en una suite y asociarlos o desasociarlos.» |
| 28 | CU06 «Validar ejecución SQL»: «gestionar el catálogo de materiales» | Texto de otro proyecto. | «El sistema verifica que haya una sola sentencia permitida, bloquea DDL/TCL y aplica las reglas del ambiente.» |
| 28 | CU07 «Ejecutar caso y suite»: «el almacenero registrar compra de materiales» | Actor y acción ajenos. | «Permite ejecutar un caso o una suite contra un perfil y clasificar cada resultado como PASS, FAIL o ERROR.» |
| 36 | Escenario de seguridad: «información de las obras» | Texto de otro proyecto. | «… sobre la información de proyectos, conexiones, casos e historial.» |
| 37 | Escenario de usabilidad: «el registro de avance de obra» | Texto de otro proyecto. | «… como obtener un primer resultado de comprobación» y medida alineada con OS‑1 (`problema-y-objetivos.md`). |
| 38 | Escenario de confidencialidad: «los datos financieros de una obra» | Texto de otro proyecto. | «… el contenido de las filas devueltas por consultas en PRODUCTION (solo se conserva la cantidad).» |

Revisión pendiente: no se leyeron las narrativas de CU01, CU08 y CU09 de FD04 ni el cuadro de costos de FD03 (§4.2, figura); conviene revisarlos con la misma lista de términos (obra, residente, almacenero, material, reactivo, laboratorio, SUNAT, entrevista, encuesta). Los diagramas de ambos PDF son imágenes y no se inspeccionaron.

## 2. Actualizaciones de contenido por esta fase

- **FD03:** añadir RF «Ejecutar una prueba rápida de un SELECT sobre un perfil guardado y mostrar el resultado explicado» (endpoint `POST /api/execute/quick`; sin DSN libre; solo SELECT; filas ocultas en PRODUCTION) y RNF de usabilidad ligado a OS‑1/OS‑2.
- **FD04:** añadir la pantalla «Inicio» (frontend `inicio.js`) y el endpoint a las vistas de procesos, implementación y a la matriz RF → componente.
- Quitar de ambos cualquier cifra de ahorro o tiempo que no esté respaldada por medición.

## 3. Cómo corregir sin perder el formato

1. Obtener la fuente editable. Opciones, de mayor a menor fidelidad:
   - **El Word original del equipo**, si alguien lo conserva fuera del repositorio (lo más probable, porque los PDF se generaron de algún `.docx`). Es la opción recomendada.
   - Los **`.docx` del commit inicial** (presumiblemente las plantillas del curso) desde el historial (`git show bfeac77:"FD03-EPIS-Informe Especificación Requerimientos.docx" > <carpeta fuera del repo>/FD03.docx`, ídem FD04): probablemente conservan el formato oficial (sin verificar), pero hay que volver a pegar el contenido actual y las figuras.
   - Convertir el PDF a Word: no recomendado (rompe tablas, numeración y figuras).
2. Aplicar las sustituciones de las tablas anteriores conservando estilos de título, numeración, pie «Fuente: Elaboración Propia» y control de versiones (subir a v1.1 o v2.0 con motivo «corrección de contenido ajeno al proyecto»).
3. Regenerar las figuras que dependan del contenido: los diagramas Mermaid de `docs/diagramas/` pueden exportarse a imagen; el ER debe actualizarse primero (usa `suite_test_cases`; la tabla real es `suite_test_case`).
4. Exportar a PDF, volver a buscar los términos de la lista y comparar el índice.
5. Guardar en el repositorio el `.docx` corregido junto al PDF, para que la próxima corrección no dependa de memoria.

Nada de esto se hizo en la Fase 1: los PDF siguen como estaban.
