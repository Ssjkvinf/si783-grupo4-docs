"""
Pruebas de la Fase 5: documentación generada desde el repositorio.

No usan Oracle ni red. Las que necesitan PyYAML se omiten si no está instalado (igual que en la Fase 3);
el flujo `docs-generate.yml` instala PyYAML y ejecuta la misma comprobación en GitHub.
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SCRIPTS_DOCS = ROOT / "scripts" / "docs"
sys.path.insert(0, str(SCRIPTS_DOCS))

import gen_docs  # noqa: E402


def _run(args, **kw):
    env = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180, **kw)


# --------------------------------------------------------------------------------------------- diccionario y esquema
def test_el_diccionario_describe_todas_las_columnas_del_modelo():
    gen_docs.check_descriptions(gen_docs.load_metadata())


def test_las_descripciones_no_incluyen_columnas_inexistentes():
    base = gen_docs.load_metadata()
    reales = {f"{t.name}.{c.name}" for t in base.metadata.sorted_tables for c in t.columns}
    assert set(gen_docs.DESC.COLUMNAS) == reales


def test_el_diccionario_coincide_con_las_migraciones(tmp_path):
    """Las columnas del modelo (de las que sale el diccionario) son las que crea `alembic upgrade head`."""
    sa = pytest.importorskip("sqlalchemy")
    db = tmp_path / "migrada.sqlite"
    env = {**__import__("os").environ, "FRAMEWORK_DB_URL": f"sqlite:///{db.as_posix()}", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=180)
    assert r.returncode == 0, r.stderr[-800:]
    insp = sa.inspect(sa.create_engine(f"sqlite:///{db.as_posix()}"))
    migradas = {f"{t}.{c['name']}" for t in insp.get_table_names() if t != "alembic_version" for c in insp.get_columns(t)}
    base = gen_docs.load_metadata()
    modelo = {f"{t.name}.{c.name}" for t in base.metadata.sorted_tables for c in t.columns}
    assert migradas == modelo


def test_el_er_incluye_la_tabla_de_asociacion_real_y_no_la_antigua():
    er = gen_docs.build_er(gen_docs.load_metadata())
    assert "suite_test_case {" in er
    assert "suite_test_cases" not in er
    assert er.splitlines()[2].strip() == "erDiagram"


def test_el_diccionario_distingue_la_base_interna_de_la_oracle_objetivo():
    md = gen_docs.build_dictionary(gen_docs.load_metadata())
    assert "## 1. Base interna (SQLite)" in md
    assert "## 2. Objetos Oracle de la demostración" in md
    assert "FRAMEWORK_TEST_ITEMS" in md
    assert "password" not in " ".join(l for l in md.splitlines() if l.startswith("| `")).lower().replace("contraseña", "")


# --------------------------------------------------------------------------------------------- diagramas
def test_los_diagramas_generados_son_deterministas():
    a = gen_docs.build_class_diagrams()
    b = gen_docs.build_class_diagrams()
    assert a == b
    assert gen_docs.build_components() == gen_docs.build_components()


def test_el_diagrama_de_clases_incluye_el_motor_y_las_estrategias():
    d = gen_docs.build_class_diagrams()["clases.mermaid"]
    for nombre in ("TargetDatabaseExecutor", "ValidationStrategy", "RowCountValidation", "ScalarValueValidation", "ExistenceValidation"):
        assert f"class {nombre} {{" in d
    assert "ValidationStrategy <|-- ScalarValueValidation" in d


def test_el_diagrama_de_componentes_se_deriva_de_los_imports():
    d = gen_docs.build_components()
    assert "app_api --> app_services" in d
    assert "app_engine --> app_security" in d
    assert "app_engine -.-> ext_oracle" in d


def test_el_diagrama_de_despliegue_lee_compose_y_workflows():
    pytest.importorskip("yaml")
    d = gen_docs.build_deployment()
    assert "caddy" in d and "oracle_db" in d and "framework_data" in d
    assert "sql-checks.yml" in d and "pages.yml" in d and "docs-generate.yml" in d


# --------------------------------------------------------------------------------------------- generación completa
def test_todo_lo_generado_esta_al_dia():
    pytest.importorskip("yaml")
    r = _run(["scripts/docs/gen_docs.py", "--check"])
    assert r.returncode == 0, r.stdout + r.stderr


def test_la_referencia_tiene_una_pagina_por_modulo():
    modulos = {gen_docs.mod_name(p) for p in gen_docs.app_modules()}
    paginas, _ = gen_docs.build_reference_pages()
    cuerpo = "\n".join(paginas.values())
    for m in modulos:
        assert f"::: {m}\n" in cuerpo, m


def test_el_bloque_del_readme_tiene_marcas_y_no_edita_el_resto():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count(gen_docs.BEGIN) == 1 and readme.count(gen_docs.END) == 1
    base = gen_docs.load_metadata()
    nuevo = gen_docs.apply_readme(readme, gen_docs.build_readme_block([("g", "/x", "GET", "s", "d")], "9.9", base))
    assert nuevo.split(gen_docs.BEGIN)[0] == readme.split(gen_docs.BEGIN)[0]
    assert nuevo.split(gen_docs.END, 1)[1] == readme.split(gen_docs.END, 1)[1]


def test_el_nav_de_mkdocs_solo_apunta_a_archivos_existentes():
    yaml = pytest.importorskip("yaml")

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_multi_constructor("!!python/", lambda l, s, n: None)
    Loader.add_multi_constructor("tag:yaml.org,2002:python/", lambda l, s, n: None)
    cfg = yaml.load((ROOT / "mkdocs.yml").read_text(encoding="utf-8"), Loader=Loader)

    def hojas(nav):
        for item in nav:
            for _, v in item.items():
                if isinstance(v, list):
                    yield from hojas(v)
                else:
                    yield v
    faltan = [h for h in hojas(cfg["nav"]) if not (ROOT / "docs" / h).exists()]
    assert not faltan, faltan


# --------------------------------------------------------------------------------------------- workflows (no se ejecutaron en GitHub)
def _wf(nombre):
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((REPO / ".github" / "workflows" / nombre).read_text(encoding="utf-8"))


def _on(doc):
    return doc.get("on", doc.get(True))


@pytest.mark.parametrize("nombre", ["docs-generate.yml", "pages.yml"])
def test_los_workflows_de_documentacion_son_yaml_valido_y_no_usan_secretos(nombre):
    doc = _wf(nombre)
    texto = (REPO / ".github" / "workflows" / nombre).read_text(encoding="utf-8")
    assert "workflow_dispatch" in _on(doc)
    assert "secrets." not in texto.replace("secrets.GITHUB_TOKEN", "")
    assert not re.search(r"azure/login|ARM_CLIENT|az login|terraform (apply|destroy)", texto)
    assert "gvenzl" not in texto  # estos flujos no levantan Oracle


def test_docs_generate_ejecuta_el_generador_sube_artefacto_resume_y_verifica_sin_escribir_en_git():
    doc = _wf("docs-generate.yml")
    texto = (REPO / ".github" / "workflows" / "docs-generate.yml").read_text(encoding="utf-8")
    assert doc["permissions"] == {"contents": "read"}
    jobs = doc["jobs"]
    assert list(jobs) == ["generar"]
    for job in jobs.values():
        assert "permissions" not in job or job["permissions"].get("contents") != "write"
    pasos = jobs["generar"]["steps"]
    corridas = [str(s.get("run", "")) for s in pasos]
    # 1) EJECUTA el generador (sin --check) y 2) más tarde verifica (--check y/o git status)
    idx_gen = next(i for i, r in enumerate(corridas) if re.search(r"gen_docs\.py(?! --check)", r) and "--check" not in r)
    idx_ver = next(i for i, r in enumerate(corridas) if "gen_docs.py --check" in r and "status --porcelain" in r)
    assert idx_gen < idx_ver
    # 3) artefacto con lo generado y 4) resumen del job
    subidas = [s for s in pasos if "upload-artifact" in str(s.get("uses", ""))]
    assert subidas and subidas[0]["with"]["name"] == "documentacion-generada"
    # el artefacto se sube ANTES de verificar, para que exista aunque la verificación falle
    assert pasos.index(subidas[0]) < idx_ver
    assert any("GITHUB_STEP_SUMMARY" in r for r in corridas)
    for destino in ("docs/generated", "docs/diagramas", "docs/referencia", "README.md"):
        assert any(destino in r for r in corridas), destino
    # sin commit, push ni add automáticos: no puede dispararse a sí mismo
    assert not re.search(r"git (push|commit|add)|git-auto-commit|contents: write", texto)


def test_pages_publica_solo_fuera_de_pull_request():
    doc = _wf("pages.yml")
    publicar = doc["jobs"]["publicar"]
    assert "pull_request" in publicar["if"] and "!=" in publicar["if"]
    assert publicar["environment"]["name"] == "github-pages"
    assert publicar["permissions"] == {"pages": "write", "id-token": "write"}
    pasos = " ".join(str(s.get("run", "")) + str(s.get("uses", "")) for s in doc["jobs"]["construir"]["steps"])
    assert "mkdocs build --strict" in pasos and "gen_docs.py --check" in pasos


@pytest.mark.parametrize("nombre", ["docs-generate.yml", "pages.yml"])
def test_los_scripts_que_invocan_los_workflows_existen(nombre):
    texto = (REPO / ".github" / "workflows" / nombre).read_text(encoding="utf-8")
    for ruta in set(re.findall(r"python (scripts/[\w/\.]+\.py)", texto)):
        assert (ROOT / ruta).exists(), ruta
    assert (ROOT / "requirements-docs.txt").exists()


def test_los_nombres_de_los_workflows_coinciden_con_las_tareas_documentadas():
    tareas = (ROOT / "docs" / "tareas-gerald.md").read_text(encoding="utf-8")
    for nombre, archivo in (("Documentación (generar)", "docs-generate.yml"), ("Documentación técnica (Pages)", "pages.yml")):
        assert nombre in tareas
        assert _wf(archivo)["name"] == nombre


# --------------------------------------------------------------------------------------------- demostración sin Oracle
def test_la_demostracion_offline_se_rotula_como_simulada_y_no_toca_el_repositorio():
    src = (ROOT / "scripts" / "demo" / "offline_demo.py").read_text(encoding="utf-8")
    ast.parse(src)
    assert "NO ES ORACLE" in src
    assert "tempfile.gettempdir()" in src
    r = _run(["scripts/demo/offline_demo.py", "ruta"])
    assert r.returncode == 0 and "framework_demo_offline" in r.stdout
    r = _run(["scripts/demo/offline_demo.py", "--help"])
    assert r.returncode == 0 and "MODO SIMULADO" in r.stdout


def test_los_informes_no_conservan_terminos_de_otras_plantillas_salvo_como_cita():
    """Los términos ajenos solo pueden aparecer en la matriz y en la propuesta de corrección, que los citan para corregirlos."""
    prohibidos = re.compile(r"\b(SUNAT|reactivos?|almacenero|residente de obra|partida nueva|avance de obra)\b", re.I)
    permitidos = {"matriz-afirmaciones.md", "LEEME.md", "FD03-fuente-corregida.md", "FD04-fuente-corregida.md"}
    for p in (ROOT / "docs" / "informes").glob("*.md"):
        if p.name in permitidos:
            continue
        assert not prohibidos.search(p.read_text(encoding="utf-8")), p.name


# --------------------------------------------------------------------------------------------- cobertura de docstrings (Fase 6)
def test_la_cobertura_de_docstrings_cambia_si_cambia_el_codigo(tmp_path, monkeypatch):
    """Un módulo nuevo con una función sin docstring debe aparecer en el informe de cobertura (y por tanto `--check` falla hasta regenerar)."""
    antes = gen_docs.build_doc_coverage()
    nuevo = ROOT / "app" / "_modulo_temporal_prueba.py"
    try:
        nuevo.write_text('"""Módulo temporal."""\n\ndef sin_docstring():\n    pass\n', encoding="utf-8")
        despues = gen_docs.build_doc_coverage()
    finally:
        nuevo.unlink(missing_ok=True)
    assert antes != despues
    assert "sin_docstring" in despues and "sin_docstring" not in antes


def test_el_informe_de_cobertura_lista_todos_los_modulos_de_app():
    md = gen_docs.build_doc_coverage()
    for p in gen_docs.app_modules():
        assert f"| `{gen_docs.mod_name(p)}` |" in md
