# Framework SQL QA (extensión de VS Code)

Integra VS Code con el Framework de pruebas SQL: ejecuta suites contra Oracle, importa casos desde Excel y exporta resultados. Usa la CLI del proyecto (`python -m app.cli`).

## Instalar
En VS Code: Extensiones → «⋯» → «Instalar desde VSIX…» y elegir `framework-sql-qa-1.0.0.vsix`.
O por terminal: `code --install-extension framework-sql-qa-1.0.0.vsix`.

## Usar
Abra el repositorio en VS Code, pulse `Ctrl+Shift+P` y escriba **SQL QA**:
- **Ejecutar suite**: pide proyecto, suite y conexión; la contraseña de Oracle se pide oculta y no se guarda. Muestra el código de salida (0 PASS, 1 FAIL, 2 ERROR…) y abre el reporte.
- **Importar casos desde Excel**: valida primero sin guardar y pregunta antes de importar.
- **Exportar resultados a Excel**.

Requisitos: Python con las dependencias del proyecto (`pip install -r requirements.txt`). Ajustes: `frameworkSql.python`, `frameworkSql.appPath`.
Seguridad: la contraseña viaja por variable de entorno (nunca por argumento) y solo se usa el ambiente TEST.
