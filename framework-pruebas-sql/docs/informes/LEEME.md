# Cómo usar las fuentes de los informes (FD01–FD05)

## Dónde están los originales (verificado el 20‑oct‑2026)

| Documento | Ubicación | Estado |
| --- | --- | --- |
| FD01, FD02, FD03, FD04, FD06 (PDF) | Raíz del repositorio (`FD0x_Informe_…_FrameworkSQL.pdf`) | **Intactos.** Subidos al repositorio en el commit «Add files via upload» |
| Fuentes editables `.docx`/`.md` de FD01–FD06 | Se eliminaron del repositorio el 06‑oct‑2026 (commits `59b1e8e`, `50f2b85`, `aeb90d0`, `ec1fc60`…) | Siguen en el historial de Git; el primer commit `bfeac77` contiene `.docx` presumiblemente de plantilla (no abiertos) |
| Plantillas `.docx` FD01–FD06 | `Downloads/proyecto-group-4-trabajo/` (copia del 21‑sep‑2026, con su `.git`) | Solo se abrió la de FD05: es la plantilla del curso, con los datos de ejemplo `{Nombre de Proyecto}` y un control de versiones de otro grupo («MPV», «10/10/2020») que debe borrarse |
| **FD06 «Propuesta del Proyecto»** | PDF en la raíz del repositorio (`FD06_Propuesta_Proyecto_FrameworkSQL.pdf`) | Es el documento de la plantilla del curso donde estaban el título, el problema con fuentes y los objetivos (lo que la consigna llama «correcciones de la semana 1»). **La consigna transcrita lista FD01–FD05; FD06 no figura como entregable de la Unidad II.** Se usó solo como **fuente** de antecedentes (cuyas URL se abrieron y verificaron). Ningún texto de FD06 se copió a FD05 como si fuera suyo; el PDF no se modificó. Si el docente no lo pide, no hace falta regenerarlo; si lo pide, la fuente es `docs/problema-y-objetivos.md` |
| **Consigna de la Unidad II y rúbrica (20 pts)** | **No existen como archivo en el repositorio ni en las carpetas revisadas.** Solo están en el mensaje del encargo; la rúbrica se conoció por capturas de pantalla de la Fase 0 | **No se pudo contrastar con un original.** Dependiente de esto: la lectura de qué puntúa el «reto» y la exigencia exacta de FD05 |
| `Downloads/EXAMEN DE UNIDAD DE PII.pdf` | Examen de otro curso (rol docente/estudiante, notas) | Sin relación con este proyecto |

## Qué hay en esta carpeta

| Archivo | Para qué |
| --- | --- |
| `matriz-afirmaciones.md` | Cada afirmación de FD01–FD04 → evidencia → veredicto → corrección |
| `FD01-parche.md`, `FD02-parche.md` | Cambios puntuales a hacer en FD01 y FD02 |
| `FD03-fuente-corregida.md`, `FD04-fuente-corregida.md` | Texto completo de las secciones a reemplazar en FD03 y FD04 |
| `FD05-informe-final.md` | Borrador del Informe Final según la plantilla oficial |

## Qué hay que regenerar (nadie lo hizo todavía)

1. Abrir la plantilla Word de cada FD (ver tabla), pegar el texto, conservar estilos y numeración, corregir el control de versiones (autores KHC/GZP, fecha completa).
2. Exportar los diagramas a imagen: `python scripts/docs/gen_docs.py` actualiza `docs/diagramas/*.mermaid`; abrirlos en <https://mermaid.live> o usar `docs/generated/diagramas.md` (o el sitio local de documentación) y exportar PNG/SVG. Quedan a mano y deben revisarse: casos de uso, actividad, secuencia.
3. Actualizar índices (los PDF tienen tablas de contenido con numeración que no coincide con el cuerpo).
4. Exportar a PDF y repetir la búsqueda de términos ajenos: `SUNAT`, `reactivo`, `laboratorio`, `obra`, `residente`, `almacenero`, `partida`, `material`, `proveedor`, `entrevista`, `encuesta`, `observación directa`, `metodolog`.
5. Guardar en el repositorio el `.docx` final junto al PDF.
