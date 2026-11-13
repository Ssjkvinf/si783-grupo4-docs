"""
Integración con VS Code (tareas, skill y extensión mínima): comprobaciones estáticas. No abre VS Code ni usa Oracle.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
EXT = REPO / "vscode-extension"


def _jsonc(ruta):
    texto = re.sub(r"^\s*//.*$", "", ruta.read_text(encoding="utf-8"), flags=re.M)
    return json.loads(texto)


def test_las_tareas_llaman_a_la_cli_y_la_clave_va_por_entorno_oculta():
    t = _jsonc(REPO / ".vscode" / "tasks.json")
    ejecutar = next(x for x in t["tasks"] if x["label"] == "SQL QA: ejecutar suite")
    assert "python -m app.cli run" in ejecutar["command"]
    assert "claveOracle" not in ejecutar["command"] and ejecutar["options"]["env"]["FW_ORACLE_PASSWORD"] == "${input:claveOracle}"
    clave = next(i for i in t["inputs"] if i["id"] == "claveOracle")
    assert clave.get("password") is True and "default" not in clave
    assert "--env TEST" in ejecutar["command"]
    for tarea in t["tasks"]:
        assert "app.cli" in tarea["command"]


def test_el_skill_prohibe_pasar_la_clave_y_otros_ambientes():
    s = (REPO / ".claude" / "skills" / "comprobaciones-sql" / "SKILL.md").read_text(encoding="utf-8")
    assert s.startswith("---\nname: comprobaciones-sql\n") and "description:" in s.split("---")[1]
    assert "Nunca" in s and "FW_ORACLE_PASSWORD" in s and "--env TEST" in s


def test_la_extension_declara_sus_comandos_y_no_lleva_secretos():
    pkg = json.loads((EXT / "package.json").read_text(encoding="utf-8"))
    declarados = {c["command"] for c in pkg["contributes"]["commands"]}
    codigo = (EXT / "extension.js").read_text(encoding="utf-8")
    for comando in declarados:
        assert f"registerCommand('{comando}'" in codigo
    assert declarados == {"frameworkSql.runSuite", "frameworkSql.importExcel", "frameworkSql.exportResults"}
    assert "FW_ORACLE_PASSWORD: clave" in codigo and "'--password'" not in codigo and "shell: false" in codigo
    assert "password: oculto" in codigo
    assert not re.search(r"(ghp_|BEGIN [A-Z ]*PRIVATE KEY)", codigo)


def test_la_extension_tiene_sintaxis_valida():
    node = shutil.which("node")
    if not node:
        pytest.skip("requiere Node.js")
    r = subprocess.run([node, "--check", str(EXT / "extension.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
