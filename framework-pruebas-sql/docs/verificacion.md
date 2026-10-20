# Verificación

## Testing Local (Pytest)
El proyecto contiene pruebas que aseguran la correcta integración de todos los componentes.
Ejecución normal sin necesidad de Oracle DB local (utiliza una SQLite temporal in-memory aislada):
```bash
pytest -q -m "not oracle_integration"
```

Ejecución de pruebas con Oracle (Requiere `RUN_ORACLE_TESTS=1` y `FRAMEWORK_TEST_PASSWORD`):
```bash
pytest -q -m oracle_integration
```

## Validación Frontend y Sintaxis
Las pruebas automáticas `test_revision_final_frontend.py` validan que la arquitectura modular `app.js` interactúe correctamente sin fugas.

## Comprobaciones de documentación y esquema (Fases 5 y 6)
Desde `framework-pruebas-sql/` (el generador y MkDocs necesitan `pip install -r requirements.txt -r requirements-docs.txt`):
```bash
python scripts/docs/gen_docs.py --check        # falla si lo generado está desactualizado
python -m mkdocs build --strict -d site        # el sitio debe construirse sin avisos
FRAMEWORK_DB_URL=sqlite:///./verificacion.sqlite alembic upgrade head   # migraciones sobre una base desechable
find frontend -name "*.js" -exec node --check {} \;
```
Los resultados con fecha y comando exacto están en `docs/informes/FD05-informe-final.md` §6.3 y en el informe de la Fase 6.
