# Resumen de una página (para explicar el proyecto en 2 minutos)

## En una frase
**Una aplicación web para comprobar que los datos de una base Oracle siguen siendo los esperados, repetir esa comprobación con un clic y guardar la evidencia de cada resultado.**

## ¿Para qué sirve?
Cuando alguien cambia una consulta, un procedimiento o los datos de una base, tiene que volver a comprobar que todo sigue bien. Hacerlo a mano es lento y no deja registro. Esta aplicación guarda esas comprobaciones («reglas»), las ejecuta cuando se pide y dice si **pasaron (PASS)**, **no coincidieron (FAIL)** o **no se pudieron ejecutar (ERROR)**, explicando por qué.

## ¿Cómo se usa? (3 pasos, sin escribir SQL)
1. **Conectar** a una base Oracle (la contraseña no se guarda).
2. **Elegir una regla** del asistente: «la tabla tiene N filas», «ninguna fila con la columna vacía», «sin valores repetidos», «la columna solo vale 0 o 1», «existe una fila con…», «los valores están en un rango».
3. **Ejecutar** y leer el resultado en lenguaje claro. Se puede guardar como caso, agrupar en una **suite** y repetir.

## ¿Qué hace más allá de un SELECT?
| Capacidad | Qué muestra |
| --- | --- |
| Reglas de calidad de datos | 8 reglas comunes con el SQL generado a la vista |
| Suite repetible | 5 reglas se ejecutan juntas; si un dato se rompe, la regla pasa a FAIL |
| **INSERT con rollback** (ambiente TEST) | Se inserta una fila de prueba, se revierte y el conteo sigue igual |
| **DROP rechazado** | La sentencia peligrosa no llega a Oracle; la tabla sigue existiendo |
| Ambientes | TEST / STAGING / PRODUCTION con reglas distintas (en PRODUCTION solo lectura y no se ven las filas) |
| Automatización | Excel (importar/exportar), línea de comandos con código de salida, flujos de GitHub Actions |
| Evidencia | Historial con SQL, esperado, obtenido, estado, duración y origen; panel «Uso del producto» |

La **Demostración guiada** (botón en «Inicio») ejecuta todo lo anterior en menos de un minuto.

## ¿Qué NO hace? (decirlo evita críticas)
- **PASS no significa «toda la base está bien»**: solo que la regla configurada se cumple.
- **Bloquear DROP es un control de seguridad, no el beneficio principal**; el rollback no cubre secuencias ni transacciones autónomas. Hace falta además una cuenta Oracle de privilegios mínimos.
- Solo Oracle 12.1 o superior. Hay cuentas individuales con roles (Administrador / Tester), pero sin recuperación por correo ni segundo factor.
- **No se midió** cuánto tiempo ahorra ni qué tan fácil es de usar: son metas, no resultados. No hay empresa cliente.

## Frente a otras herramientas (comparación de lo que declaran, sin pruebas de uso)
| Herramienta | Enfoque | En qué se parece / se diferencia |
| --- | --- | --- |
| [utPLSQL](https://github.com/utPLSQL/utPLSQL) | Pruebas unitarias de código PL/SQL, por código y línea de comandos | Es para probar *programas* PL/SQL; la nuestra comprueba *datos* con reglas y una interfaz web |
| Oracle SQL Developer Unit Test | Suites de pruebas dentro de una aplicación de escritorio | Similar en suites y resultados; la nuestra es web, con política por ambiente, Excel y panel de uso |
| [Soda Core](https://www.cybersierra.co/blog/best-data-quality-tools) / dbt tests | Reglas de calidad de datos en YAML o SQL (`not_null`, `unique`…) | Misma idea de «reglas listas»; nosotros las generamos para Oracle desde una pantalla |
| [RegreSQL](https://github.com/boringSQL/regresql) | Compara resultados esperados y exporta JUnit | Coincide con nuestra salida JUnit y los códigos de salida para CI |

## Cómo mostrarlo en 3 minutos
`docs/demostracion-sustentacion.md`: Demostración guiada → asistente de reglas con un caso propio → historial y panel de uso.
