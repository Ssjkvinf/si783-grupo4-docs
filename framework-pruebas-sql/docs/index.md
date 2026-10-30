# Framework de pruebas SQL — documentación técnica

Aplicación web para **repetir comprobaciones SQL sobre Oracle y conservar su evidencia de ejecución** (proyecto académico, Tacna, 2026). No existe organización cliente; la utilidad de la herramienta **no se midió**.

Esta documentación se genera desde el repositorio con `scripts/docs/gen_docs.py` y `mkdocs`:

- **Informes**: fuentes editables de FD01–FD05 y la matriz de afirmaciones.
- **Documentación generada**: diccionario de datos, diagramas (ER, clases, componentes, despliegue) y endpoints de la API.
- **Referencia del código**: clases, métodos y propiedades de `app/`, tomados de los docstrings.
- **Manuales y demostración**: instalación, operación, seguridad, guion y preguntas del jurado.

Dos bases distintas: la **base interna** (SQLite: metadatos e historial) y la **base objetivo** (Oracle: la que se comprueba).
