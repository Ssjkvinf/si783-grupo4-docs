# Protocolo para medir el «primer resultado» (antes y después)

Meta a comprobar (OS‑1 y OS‑2 de `problema-y-objetivos.md`): una persona nueva completa su primera comprobación en pocos minutos y entiende el resultado. **Es una meta, no un resultado alcanzado.** Con 3–5 personas solo se obtienen datos descriptivos: no se afirma significancia estadística ni mejora porcentual general.

## 1. Participantes

- 3 a 5 compañeros por condición (antes / después), que **no** hayan participado en el desarrollo ni visto la aplicación.
- Lo ideal es que sean personas distintas en cada condición (si una misma persona hace las dos, ya conoce la aplicación y sesga el «después»). Si no hay suficientes, alternar el orden y usar una consulta distinta en cada condición, y anotarlo.
- Identificarlos como P1, P2… No guardar nombres ni datos personales. Pedir consentimiento verbal para anotar tiempos y, si se desea, grabar la pantalla.

## 2. Condiciones

| | Antes | Después |
| --- | --- | --- |
| Versión | Interfaz anterior (commit `34831a4`) | Interfaz con «Inicio» (esta fase) |
| Cómo ejecutarla | Despliegue anterior en Azure **si sigue disponible** (no verificado), o clon aparte: `git clone <ruta del repo> ..\baseline` y `git -C ..\baseline checkout 34831a4` (en otra carpeta; no toca este repositorio) | `uvicorn app.main:app` desde `framework-pruebas-sql` |
| Base Oracle | La misma base de demostración para ambas condiciones | La misma |
| Punto de partida | Aplicación abierta en el navegador, con sesión iniciada, **sin** conexiones ni casos creados | Igual |

La persona que dirige la sesión entrega la contraseña de Oracle en un papel o mensaje privado; **no** se escribe en el repositorio ni en la hoja de registro.

## 3. Tarea que se entrega (texto fijo)

> «Esta aplicación sirve para comprobar consultas sobre una base Oracle. Tiene la dirección de la base y su contraseña en este papel. Compruebe que la tabla de demostración responde y dígame si la comprobación pasó o no, y por qué.»

No se explica ningún módulo ni se señala dónde hacer clic. El observador solo interviene si la persona lleva 3 minutos sin avanzar (se anota como «ayuda»).

## 4. Qué se mide

| Medida | Cómo | Para la meta |
| --- | --- | --- |
| T1: tiempo hasta ver el primer resultado | Cronómetro: desde que la persona recibe la tarea hasta que aparece PASS/FAIL/ERROR | OS‑1 (≤ 5 min) |
| Clics y pantallas visitadas | Observador o grabación de pantalla | Apoyo |
| Ayudas pedidas / intervenciones del observador | Contador | OS‑1 (sin intervención) |
| Errores de la persona (campos mal llenados, vuelta atrás) | Lista breve | Apoyo |
| Comprensión (pregunta fija): «¿Qué esperaba la comprobación, qué obtuvo y por qué salió así?» | Respuesta anotada literalmente; se califica correcta/parcial/incorrecta con la clave de abajo | OS‑2 (≥ 80 % correctas) |
| Comentario libre: «¿Qué cambiaría?» | Anotar | Cualitativo |

**Clave de calificación de la pregunta de comprensión:** *correcta* si dice qué se esperaba y qué se obtuvo y reconoce si coinciden; *parcial* si solo cumple una parte; *incorrecta* en otro caso. Calificar sin conocer a qué condición pertenece la respuesta, si es posible (hacerlo dos compañeros por separado y reconciliar).

## 5. Hoja de registro

Una fila por participante; copiar una tabla por condición.

| Participante | Condición | T1 (mm:ss) | Clics | Ayudas | Errores | Comprensión (C/P/I) | Comentario |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P1 | Antes | | | | | | |
| P2 | Antes | | | | | | |
| P3 | Antes | | | | | | |
| P1′ | Después | | | | | | |
| P2′ | Después | | | | | | |
| P3′ | Después | | | | | | |

## 6. Cómo reportarlo

- Para cada condición: mediana y rango de T1, número de participantes que terminaron sin ayuda, y porcentaje de comprensión correcta (con n visible, por ejemplo «3 de 4»).
- Comparar con las metas OS‑1 y OS‑2 y decir si se cumplieron **en esta muestra**.
- Declarar las limitaciones: muestra pequeña, compañeros de la misma carrera, una sola tarea, el observador es parte del equipo.
- Conservar las hojas completas y las capturas como evidencia. No presentar la reducción de tiempo como ahorro económico.

## 7. Resultados (completar tras las sesiones)

_Pendiente: aún no se han realizado las sesiones. No hay datos de usuarios en este repositorio._
