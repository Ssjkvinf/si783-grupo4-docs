#!/usr/bin/env python3
"""
Generador de documentación técnica a partir del repositorio (sin datos escritos a mano salvo las
descripciones de columnas de `descripciones_datos.py`).

Genera, de forma reproducible (misma entrada -> misma salida, sin fechas):

  docs/generated/diccionario-datos.md   diccionario de datos (SQLite interna + objetos Oracle de la demo)
  docs/generated/api-endpoints.md       endpoints leídos de la aplicación FastAPI
  docs/generated/diagramas.md           los diagramas anteriores incrustados (para GitHub Pages)
  docs/diagramas/base_datos.mermaid     ER de la SQLite interna (desde los modelos SQLAlchemy)
  docs/diagramas/clases.mermaid         clases del motor, la seguridad y los servicios (desde el código)
  docs/diagramas/clases_modelos.mermaid clases ORM y sus relaciones
  docs/diagramas/clases_schemas.mermaid clases Pydantic (entrada/salida de la API)
  docs/diagramas/componentes.mermaid    dependencias entre paquetes (desde los imports)
  docs/diagramas/despliegue.mermaid     compose de producción, Terraform y workflows
  docs/referencia/*.md                  una página por módulo para mkdocstrings (clases, métodos, propiedades)
  mkdocs.yml                            configuración del sitio (la navegación sale de los módulos)
  README.md                             solo el bloque entre las marcas GENERADO

Uso (desde framework-pruebas-sql/):
  python scripts/docs/gen_docs.py            escribe los archivos
  python scripts/docs/gen_docs.py --check    no escribe: falla (código 1) si algún archivo generado está desactualizado

No necesita Oracle, red ni Docker. Requiere las dependencias de la aplicación y PyYAML.
"""
import argparse
import ast
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import descripciones_datos as DESC  # noqa: E402

NL = chr(10)
BEGIN = "<!-- GENERADO:inicio resumen -->"
END = "<!-- GENERADO:fin resumen -->"
CABECERA_MD = "<!-- GENERADO por scripts/docs/gen_docs.py. No editar a mano: edite el código o descripciones_datos.py y vuelva a ejecutarlo. -->\n\n"
CABECERA_MMD = "%% GENERADO por scripts/docs/gen_docs.py. No editar a mano.\n"


# ----------------------------------------------------------------------------------------------- utilidades
def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def app_modules():
    """Rutas de los módulos de app/ en orden estable."""
    return sorted(p for p in (ROOT / "app").rglob("*.py") if "__pycache__" not in p.parts)


def mod_name(p: Path) -> str:
    parts = list(p.relative_to(ROOT).with_suffix("").parts)
    return ".".join(parts)


def parse(p: Path) -> ast.Module:
    return ast.parse(p.read_text(encoding="utf-8"), filename=str(p))


def md_escape(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def safe_id(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", s)


# ----------------------------------------------------------------------------------------------- modelos ORM
def load_metadata():
    from app.core.database import Base
    from app.models import project, connection, test_case, suite, history, usage, user  # noqa: F401
    return Base


def default_text(col):
    d = col.default
    if d is None:
        return ""
    arg = getattr(d, "arg", None)
    if callable(arg):
        n = getattr(arg, "__name__", "")
        return "(función de la aplicación: %s)" % ("fecha y hora actual UTC" if n in ("get_utc_now", "utcnow") else n + "()")
    return repr(arg)


def column_type(col) -> str:
    return str(col.type)


def check_descriptions(base):
    faltan, sobran = [], []
    reales = set()
    for t in base.metadata.sorted_tables:
        if t.name not in DESC.TABLAS:
            faltan.append(t.name)
        for c in t.columns:
            k = f"{t.name}.{c.name}"
            reales.add(k)
            if k not in DESC.COLUMNAS:
                faltan.append(k)
    for k in DESC.COLUMNAS:
        if k not in reales:
            sobran.append(k)
    for t in DESC.TABLAS:
        if t not in base.metadata.tables:
            sobran.append(t)
    if faltan or sobran:
        raise SystemExit("Diccionario incompleto. Sin descripción: %s. Descripciones que sobran: %s" % (faltan, sobran))


def parse_oracle_changelog():
    """Lee la tabla, el índice y la vista del changelog de Liquibase (formato SQL)."""
    d = ROOT / "infra" / "oracle" / "liquibase" / "changelog"
    tablas, otros = {}, []
    for f in sorted(d.glob("*.sql")):
        txt = f.read_text(encoding="utf-8")
        m = re.search(r"CREATE TABLE (\w+)\s*\((.*?)\);", txt, re.S | re.I)
        if m:
            cols = []
            for line in m.group(2).split(","):
                line = " ".join(line.split())
                if not line:
                    continue
                name, rest = line.split(" ", 1)
                cols.append((name, rest))
            tablas[m.group(1)] = cols
        for kind, name, tail in re.findall(r"CREATE (?:OR REPLACE )?(INDEX|VIEW) (\w+)\s+(.*?);", txt, re.S | re.I):
            otros.append((kind.upper(), name, " ".join(tail.split()), f.name))
    return tablas, otros


def build_dictionary(base) -> str:
    from app.models import schemas
    from app.services.usage_service import ORIGENES
    md = [CABECERA_MD, "# Diccionario de datos\n"]
    md.append("Este diccionario se genera desde los modelos SQLAlchemy (`app/models/*.py`) y el changelog de Liquibase "
              "(`infra/oracle/liquibase/changelog/`). Hay **dos bases distintas**:\n")
    md.append("| Base | Motor | Qué guarda | Versionada con | Sección |\n| --- | --- | --- | --- | --- |")
    md.append("| **Interna de la aplicación** | SQLite (`FRAMEWORK_DB_URL`) | Metadatos: proyectos, perfiles de conexión (sin contraseña), casos, suites, historial, eventos de uso | Alembic (`alembic/versions/`) | 1 |")
    md.append("| **Objetivo** | Oracle (la que se comprueba) | Los datos del usuario sobre los que se ejecutan los casos. La aplicación **no** es dueña de esos datos; solo se versiona con Liquibase el objeto de la **demostración** | Liquibase (`infra/oracle/liquibase/`) | 2 |\n")
    md.append("## 1. Base interna (SQLite)\n")
    md.append("Las fechas `created_at/updated_at` de `test_cases` y `test_suites` se guardan en UTC **sin** zona horaria; las demás tablas usan UTC con zona horaria. Es una inconsistencia real del código, no un error de este documento.\n")
    for t in base.metadata.sorted_tables:
        md.append(f"### `{t.name}`\n")
        md.append(DESC.TABLAS[t.name] + "\n")
        md.append("| Columna | Tipo | Nulo | Clave | Por defecto (en la aplicación) | Índice | Descripción |\n| --- | --- | --- | --- | --- | --- | --- |")
        indexed = {c.name for ix in t.indexes for c in ix.columns}
        for c in t.columns:
            keys = []
            if c.primary_key:
                keys.append("PK")
            for fk in c.foreign_keys:
                keys.append(f"FK → {fk.target_fullname}")
            if c.unique:
                keys.append("único")
            idx = "sí" if (c.name in indexed and not c.primary_key) else ""
            md.append("| `{}` | {} | {} | {} | {} | {} | {} |".format(
                c.name, column_type(c), "sí" if c.nullable else "no", md_escape(", ".join(keys)),
                md_escape(default_text(c)), idx, md_escape(DESC.COLUMNAS[f"{t.name}.{c.name}"])))
        md.append("")
    # Relaciones y borrado en cascada (desde los mappers)
    md.append("### Relaciones y borrado en cascada\n")
    md.append("| Desde | Hacia | Cascada de borrado (ORM) |\n| --- | --- | --- |")
    from sqlalchemy.orm import configure_mappers
    configure_mappers()
    filas = []
    for mapper in base.registry.mappers:
        for r in mapper.relationships:
            if r.direction.name == "ONETOMANY":
                filas.append((mapper.class_.__name__, r.mapper.class_.__name__, "sí" if r.cascade.delete else "no (se rechaza o queda dependiente)"))
    for a, b, c in sorted(filas):
        md.append(f"| {a} | {b} | {c} |")
    md.append("\nEl borrado en cascada solo lo hace el ORM al eliminar un proyecto; los endpoints de borrado rechazan eliminar proyectos, suites o casos con dependencias (ver `docs/seguridad.md`).\n")

    md.append("### Dominios de valores\n")
    md.append("| Campo | Valores | Fuente |\n| --- | --- | --- |")
    md.append("| `test_cases.validation_type` | " + ", ".join(f"`{m.value}`" for m in schemas.ValidationTypeEnum) + " | `ValidationTypeEnum` en `app/models/schemas.py` |")
    md.append("| `connection_profiles.environment_type` | " + ", ".join(f"`{m.value}`" for m in schemas.EnvironmentTypeEnum) + " | `EnvironmentTypeEnum` en `app/models/schemas.py` |")
    md.append("| `execution_history.status` | `PASS`, `FAIL`, `ERROR` | `app/api/history.py` (filtro) y `execution_service.py` |")
    md.append("| `execution_history.trigger_source` | " + ", ".join(f"`{k}`" for k in sorted(ORIGENES)) + " (vacío = anterior a la Fase 4) | `ORIGENES` en `app/services/usage_service.py` |")
    tipos = sorted(set(re.findall(r'record_event\(\s*db,\s*"([a-z_]+)"', "\n".join(p.read_text(encoding="utf-8") for p in app_modules()))))
    md.append("| `usage_events.event_type` | " + ", ".join(f"`{t}`" for t in tipos) + " | llamadas a `record_event` en `app/` |\n")

    tablas, otros = parse_oracle_changelog()
    md.append("## 2. Objetos Oracle de la demostración (esquema `FRAMEWORK_TEST`)\n")
    md.append("Solo lo que versiona Liquibase. Son datos de **ejemplo** para las reglas de calidad de la demostración; la aplicación puede apuntar a cualquier otra base Oracle y no conoce su esquema.\n")
    for t, cols in sorted(tablas.items()):
        md.append(f"### `{t}`\n")
        md.append(DESC.ORACLE_TABLAS.get(t, "(sin descripción)") + "\n")
        md.append("| Columna | Definición Oracle | Descripción |\n| --- | --- | --- |")
        for name, rest in cols:
            md.append("| `{}` | `{}` | {} |".format(name, rest, md_escape(DESC.ORACLE_COLUMNAS.get(f"{t}.{name}", "(sin descripción)"))))
        md.append("")
    md.append("| Objeto | Tipo | Definición | Changeset (archivo) | Descripción |\n| --- | --- | --- | --- | --- |")
    for kind, name, tail, fname in otros:
        md.append("| `{}` | {} | `{}` | `{}` | {} |".format(name, kind, md_escape(tail), fname, md_escape(DESC.ORACLE_OTROS.get(name, ""))))
    faltan = [t for t in tablas if t not in DESC.ORACLE_TABLAS] + [n for _, n, _, _ in otros if n not in DESC.ORACLE_OTROS]
    if faltan:
        raise SystemExit(f"Objetos Oracle sin descripción: {faltan}")
    md.append("\nLa prueba `test_oracle_phase2.py` crea además, solo en un Oracle desechable, la tabla `FW_OWNER.CANARY` para comprobar el rechazo de `DROP`; no forma parte del esquema versionado.\n")
    return "\n".join(md)


def build_er(base) -> str:
    out = [CABECERA_MMD + "%% Base INTERNA (SQLite): metadatos e historial. No incluye la base Oracle objetivo.", "erDiagram"]
    for t in base.metadata.sorted_tables:
        out.append(f"    {t.name} {{")
        for c in t.columns:
            tipo = re.sub(r"\(.*\)", "", column_type(c)).replace(" ", "_")
            marks = []
            if c.primary_key:
                marks.append("PK")
            if c.foreign_keys:
                marks.append("FK")
            out.append(f"        {tipo} {c.name}" + (" " + ",".join(marks) if marks else ""))
        out.append("    }")
    for t in base.metadata.sorted_tables:
        for c in t.columns:
            for fk in c.foreign_keys:
                parent = fk.column.table.name
                left = "||" if not c.nullable else "|o"
                # Tabla de asociación: ambas FK son parte de la PK -> relación uno a muchos hacia la tabla puente
                out.append(f'    {parent} {left}--o{{ {t.name} : "{c.name}"')
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------------- clases (AST)
def simple_type(ann):
    if ann is None:
        return ""
    if isinstance(ann, ast.Name):
        return ann.id
    if isinstance(ann, ast.Attribute):
        return ann.attr
    if isinstance(ann, ast.Subscript):
        outer = simple_type(ann.value)
        inner = ann.slice
        if isinstance(inner, ast.Tuple):
            inner = inner.elts[0] if inner.elts else None
        inn = inner.id if isinstance(inner, ast.Name) else (inner.attr if isinstance(inner, ast.Attribute) else "")
        return f"{outer}~{inn}~" if inn else outer
    return ""


def collect_classes(files):
    classes = []
    for p in files:
        tree = parse(p)
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = []
            for b in node.bases:
                bases.append(b.id if isinstance(b, ast.Name) else (b.attr if isinstance(b, ast.Attribute) else ""))
            attrs, methods, rels = [], [], []
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    attrs.append((item.target.id, simple_type(item.annotation)))
                elif isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
                    n = item.targets[0].id
                    if n.startswith("__"):
                        continue
                    v = item.value
                    fn = v.func.id if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) else ""
                    if fn == "Column":
                        tipo = ""
                        for a in v.args:
                            if isinstance(a, ast.Name):
                                tipo = a.id
                            elif isinstance(a, ast.Call) and isinstance(a.func, ast.Name) and a.func.id not in ("ForeignKey",):
                                tipo = a.func.id
                            if tipo:
                                break
                        attrs.append((n, tipo))
                    elif fn == "relationship":
                        target = v.args[0].value if v.args and isinstance(v.args[0], ast.Constant) else ""
                        rels.append((n, target))
                elif isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    abstract = any((isinstance(d, ast.Name) and d.id == "abstractmethod") for d in item.decorator_list)
                    if item.name.startswith("_") and item.name != "__init__":
                        continue
                    args = [a.arg for a in item.args.args if a.arg not in ("self", "cls")]
                    ret = simple_type(item.returns)
                    methods.append((item.name, args, ret, abstract))
                    if item.name == "__init__":
                        for sub in ast.walk(item):
                            if isinstance(sub, ast.Assign):
                                for tg in sub.targets:
                                    if isinstance(tg, ast.Attribute) and isinstance(tg.value, ast.Name) and tg.value.id == "self" and not tg.attr.startswith("_"):
                                        if tg.attr not in [a for a, _ in attrs]:
                                            attrs.append((tg.attr, ""))
            doc = ast.get_docstring(node) or ""
            classes.append({"name": node.name, "bases": bases, "attrs": attrs, "methods": methods, "rels": rels,
                            "file": rel(p), "abstract": any(m[3] for m in methods) or "ABC" in bases, "doc": doc.split("\n")[0]})
    return classes


def class_diagram(classes, titulo) -> str:
    names = {c["name"] for c in classes}
    out = [CABECERA_MMD + f"%% {titulo}", "classDiagram"]
    for c in classes:
        out.append(f"    class {safe_id(c['name'])} {{")
        if c["abstract"]:
            out.append("        <<abstract>>")
        for n, t in c["attrs"]:
            out.append(f"        +{t + ' ' if t else ''}{n}")
        for n, args, ret, _ in c["methods"]:
            if n == "__init__":
                continue
            out.append(f"        +{n}({', '.join(args)}){' ' + ret if ret else ''}")
        out.append("    }")
    for c in classes:
        for b in c["bases"]:
            if b in names:
                out.append(f"    {safe_id(b)} <|-- {safe_id(c['name'])}")
    for c in classes:
        for n, target in c["rels"]:
            if target in names:
                out.append(f'    {safe_id(c["name"])} --> {safe_id(target)} : {n}')
    return "\n".join(out) + "\n"


def build_class_diagrams():
    mods = app_modules()
    orm_files = [ROOT / "app" / "models" / f for f in ("project.py", "connection.py", "test_case.py", "suite.py", "history.py", "usage.py")]
    schema_file = [ROOT / "app" / "models" / "schemas.py"]
    motor_files = [p for p in mods if p.relative_to(ROOT).parts[1] in ("engine", "security", "services", "core") or p.name == "cli.py"]
    orm = [c for c in collect_classes(orm_files)]
    sch = collect_classes(schema_file)
    motor = collect_classes(motor_files)
    return {
        "clases.mermaid": class_diagram(motor, "Clases del motor de ejecución, la seguridad y los servicios (app/engine, app/security, app/services, app/core)"),
        "clases_modelos.mermaid": class_diagram(orm, "Clases ORM de la base interna SQLite (app/models)"),
        "clases_schemas.mermaid": class_diagram(sch, "Clases Pydantic de entrada y salida de la API (app/models/schemas.py)"),
    }


# ----------------------------------------------------------------------------------------------- componentes
EXTERNAS = {
    "oracledb": ("ext_oracle", "Oracle objetivo (python-oracledb)"),
    "sqlparse": ("ext_sqlparse", "sqlparse"),
    "openpyxl": ("ext_openpyxl", "openpyxl (Excel)"),
    "sqlalchemy": ("ext_sqlite", "SQLite interna (SQLAlchemy)"),
    "fastapi": ("ext_fastapi", "FastAPI"),
}


def package_of(modname: str) -> str:
    parts = modname.split(".")
    return ".".join(parts[:2]) if len(parts) >= 3 else modname


def build_components() -> str:
    edges = Counter()
    ext_edges = Counter()
    sources = [(mod_name(p), parse(p)) for p in app_modules()]
    alembic_env = ROOT / "alembic" / "env.py"
    if alembic_env.exists():
        sources.append(("alembic", parse(alembic_env)))
    pkgs = set()
    for name, tree in sources:
        src = package_of(name) if name != "alembic" else "alembic"
        pkgs.add(src)
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.ImportFrom) and node.module:
                targets.append(node.module)
            elif isinstance(node, ast.Import):
                targets.extend(a.name for a in node.names)
            for t in targets:
                root_mod = t.split(".")[0]
                if root_mod == "app":
                    dst = package_of(t if t.count(".") >= 2 else t)
                    if dst == "app" or dst == src:
                        continue
                    # `from app.api import projects` -> dst = app.api
                    edges[(src, dst)] += 1
                elif root_mod in EXTERNAS and root_mod != "fastapi":
                    # SQLAlchemy lo usan casi todos los paquetes: solo se dibuja desde el núcleo y las migraciones (legibilidad).
                    if root_mod == "sqlalchemy" and src not in ("app.core", "alembic"):
                        continue
                    ext_edges[(src, root_mod)] += 1
    for (a, b) in list(edges):
        pkgs.add(b)
    front = ROOT / "frontend"
    n_js = len(list(front.rglob("*.js"))) if front.exists() else 0
    main_src = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    sirve_ui = "StaticFiles" in main_src
    out = [CABECERA_MMD + "%% Dependencias entre paquetes, leídas de los import de app/ y alembic/env.py (se omiten FastAPI y, salvo en app.core y alembic, SQLAlchemy por legibilidad).", "flowchart LR"]
    out.append(f'    nav["Navegador: frontend/ ({n_js} archivos JS)"]')
    out.append('    subgraph APP["Aplicación Python (app/)"]')
    for p in sorted(x for x in pkgs if x != "alembic"):
        out.append(f'        {safe_id(p)}["{p}"]')
    out.append("    end")
    if "alembic" in pkgs:
        out.append('    alembic["alembic/ (migraciones)"]')
    used_ext = sorted({e for (_, e) in ext_edges})
    for e in used_ext:
        out.append(f'    {EXTERNAS[e][0]}[("{EXTERNAS[e][1]}")]')
    out.append('    nav -->|"HTTP /api"| app_main')
    if sirve_ui:
        out.append('    app_main -->|"sirve /ui"| nav')
    for (a, b), n in sorted(edges.items()):
        out.append(f'    {safe_id(a)} --> {safe_id(b)}')
    for (a, e), n in sorted(ext_edges.items()):
        out.append(f'    {safe_id(a)} -.-> {EXTERNAS[e][0]}')
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------------- despliegue
def build_deployment() -> str:
    import yaml
    compose = yaml.safe_load((ROOT / "infra" / "production" / "compose.yml").read_text(encoding="utf-8"))
    tf = defaultdict(list)
    for f in sorted((ROOT / "infra" / "terraform").glob("*.tf")):
        for kind, typ, name in re.findall(r'^(resource|data)\s+"([^"]+)"\s+"([^"]+)"', f.read_text(encoding="utf-8"), re.M):
            tf[f.name].append((kind, typ, name))
    wfs = []
    for f in sorted((REPO / ".github" / "workflows").glob("*.yml")):
        d = yaml.safe_load(f.read_text(encoding="utf-8"))
        on = d.get("on", d.get(True, {})) or {}
        triggers = sorted(on.keys()) if isinstance(on, dict) else [str(on)]
        wfs.append((f.name, d.get("name", f.name), triggers))
    out = [CABECERA_MMD + "%% Leído de infra/production/compose.yml, infra/terraform/*.tf y .github/workflows/*.yml (no verifica que exista en Azure).", "flowchart TB"]
    out.append('    user(["Persona usuaria (navegador)"])')
    out.append('    subgraph VM["Máquina virtual Linux (Docker Compose: infra/production/compose.yml)"]')
    for name, svc in sorted(compose["services"].items()):
        img = str(svc.get("image", "")).split("@")[0]
        ports = ", ".join(str(p) for p in svc.get("ports", []))
        label = f"{name}<br/>{img}" + (f"<br/>puertos {ports}" if ports else "")
        out.append(f'        {safe_id(name)}["{label}"]')
    out.append("    end")
    for vol in sorted(compose.get("volumes", {})):
        users = [n for n, s in compose["services"].items() if any(str(v).startswith(vol + ":") for v in s.get("volumes", []))]
        out.append(f'    {safe_id("vol_" + vol)}[("volumen {vol}")]')
        for u in users:
            out.append(f"    {safe_id(u)} --- {safe_id('vol_' + vol)}")
    out.append('    user -->|"HTTPS 443"| caddy')
    out.append('    caddy -->|"proxy a api:8000"| api')
    out.append('    api -->|"oracledb"| oracle_db')
    out.append('    api -->|"SQLAlchemy"| vol_framework_data')
    out.append('    subgraph TF["Terraform (infra/terraform/)"]')
    for f, items in sorted(tf.items()):
        if not items:
            continue
        txt = "<br/>".join(f"{k} {t}.{n}" for k, t, n in items)
        out.append(f'        {safe_id("tf_" + f)}["{f}<br/>{txt}"]')
    out.append("    end")
    out.append('    subgraph GH["GitHub Actions (.github/workflows/)"]')
    for f, nm, trig in wfs:
        out.append(f'        {safe_id("wf_" + f)}["{f}<br/>{",".join(trig)}"]')
    out.append("    end")
    out.append('    TF -.->|"gestiona/consulta"| VM')
    out.append('    GH -.->|"construye, prueba, despliega"| VM')
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------------------------- endpoints
def build_endpoints():
    """Lee las rutas del esquema OpenAPI de la aplicación (independiente de cómo FastAPI organice sus routers)."""
    from app.main import app
    schema = app.openapi()
    rows = []
    for path, ops in schema.get("paths", {}).items():
        for method, op in ops.items():
            if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                continue
            desc = (op.get("description") or "").strip().split(NL)[0]
            rows.append((", ".join(op.get("tags", [])), path, method.upper(), op.get("summary", ""), desc))
    rows.sort()
    md = [CABECERA_MD, "# Endpoints de la API" + NL,
          f"Leídos del esquema OpenAPI de la aplicación FastAPI (`app.main:app`, versión {app.version}). Total: **{len(rows)}** operaciones documentadas. "
          "No incluye `/ui/` (archivos estáticos), `/login` (página) ni `/` (redirección)." + NL,
          "La documentación interactiva está en `/docs` cuando la aplicación está en marcha." + NL,
          "| Grupo | Método | Ruta | Resumen | Descripción (primera línea del docstring) |" + NL + "| --- | --- | --- | --- | --- |"]
    for tags, path, method, summary, desc in rows:
        md.append(f"| {md_escape(tags)} | {method} | `{path}` | {md_escape(summary)} | {md_escape(desc)} |")
    return NL.join(md) + NL, rows, app.version


# ----------------------------------------------------------------------------------------------- referencia + mkdocs
def build_reference_pages():
    pages = {}
    index = [CABECERA_MD, "# Referencia del código\n",
             "Clases, métodos y propiedades generados con *mkdocstrings* a partir de los docstrings y las anotaciones del código de `app/`. "
             "Solo se documenta Python; el frontend (JavaScript) no está incluido.\n", "| Módulo | Descripción |", "| --- | --- |"]
    nav = []
    for p in app_modules():
        name = mod_name(p)
        tree = parse(p)
        doc = (ast.get_docstring(tree) or "").strip().split("\n")[0]
        fname = name.replace("app.", "", 1) if name != "app" else "app"
        fname = fname.replace(".", "_") + ".md"
        pages[f"docs/referencia/{fname}"] = CABECERA_MD + f"# `{name}`\n\n::: {name}\n    options:\n      show_root_heading: false\n      show_source: false\n      members_order: source\n"
        index.append(f"| [`{name}`]({fname}) | {md_escape(doc)} |")
        nav.append((name, f"referencia/{fname}"))
    pages["docs/referencia/index.md"] = "\n".join(index) + "\n"
    return pages, nav


NAV_FIJA = [
    ("Inicio", "index.md"),
    ("Informes (fuentes editables)", [
        ("Cómo usar estas fuentes", "informes/LEEME.md"),
        ("Matriz de afirmaciones FD01–FD04", "informes/matriz-afirmaciones.md"),
        ("Corrección de FD03 y FD04 (Fase 1)", "correccion-fd03-fd04.md"),
        ("FD01 (parche)", "informes/FD01-parche.md"),
        ("FD02 (parche)", "informes/FD02-parche.md"),
        ("FD03 (fuente corregida)", "informes/FD03-fuente-corregida.md"),
        ("FD04 (fuente corregida)", "informes/FD04-fuente-corregida.md"),
        ("FD05 Informe final (borrador)", "informes/FD05-informe-final.md"),
    ]),
    ("Resumen de una página", "resumen-una-pagina.md"),
    ("Problema y objetivos", "problema-y-objetivos.md"),
    ("Estándar de programación", "estandar-programacion.md"),
    ("Manuales", [
        ("Manual de usuario", "manual-usuario.md"),
        ("Manual técnico", "manual-tecnico.md"),
        ("Arquitectura (resumen)", "arquitectura.md"),
        ("Matriz de trazabilidad", "matriz-trazabilidad.md"),
        ("Referencia SRS y SAD", "referencia-srs-sad.md"),
        ("Verificación", "verificacion.md"),
        ("Instalación local", "instalacion-local.md"),
        ("Despliegue", "despliegue.md"),
        ("Seguridad", "seguridad.md"),
        ("Respaldo y restauración", "respaldo-restauracion.md"),
        ("Operación (Fase 3)", "operacion-fase3.md"),
        ("Runbook de Azure (paso a paso)", "runbook-azure.md"),
        ("Integraciones (Fase 4)", "integraciones-fase4.md"),
    ]),
    ("Documentación generada", [
        ("Diccionario de datos", "generated/diccionario-datos.md"),
        ("Diagramas", "generated/diagramas.md"),
        ("Endpoints de la API", "generated/api-endpoints.md"),
        ("Cobertura de docstrings", "generated/cobertura-docstrings.md"),
    ]),
    ("Demostración", [
        ("Guion y preguntas del jurado", "demostracion-sustentacion.md"),
        ("Demostración de la Fase 2", "demostracion-fase2.md"),
        ("Protocolo de usabilidad", "protocolo-usabilidad.md"),
        ("Evaluación del reto de integración", "evaluacion-reto-integracion.md"),
        ("Publicación en GitHub", "publicacion-github.md"),
        ("Tareas para Gerald", "tareas-gerald.md"),
    ]),
]


def yaml_nav(items, indent=2):
    pad = " " * indent
    out = []
    for title, target in items:
        if isinstance(target, list):
            out.append(f"{pad}- {title}:")
            out.extend(yaml_nav(target, indent + 4))
        else:
            out.append(f"{pad}- {title}: {target}")
    return out


def build_mkdocs(ref_nav):
    nav = list(NAV_FIJA) + [("Referencia del código", [("Índice", "referencia/index.md")] + ref_nav)]
    head = [
        "# GENERADO por scripts/docs/gen_docs.py (la navegación sale de los módulos de app/). Para cambiar la parte fija edite NAV_FIJA en ese script.",
        "site_name: Framework de pruebas SQL — documentación técnica",
        "site_description: Documentación generada desde el repositorio (clases, métodos, propiedades, diccionario de datos y diagramas).",
        "docs_dir: docs",
        "site_dir: site",
        "theme:",
        "  name: material",
        "  language: es",
        "  font: false",
        "markdown_extensions:",
        "  - tables",
        "  - admonition",
        "  - toc:",
        "      permalink: true",
        "  - pymdownx.superfences:",
        "      custom_fences:",
        "        - name: mermaid",
        "          class: mermaid",
        "          format: !!python/name:pymdownx.superfences.fence_code_format",
        "plugins:",
        "  - search",
        "  - mkdocstrings:",
        "      handlers:",
        "        python:",
        "          paths: [.]",
        "          options:",
        "            docstring_style: google",
        "            show_if_no_docstring: true",
        "            filters: ['!^_']",
        "validation:",
        "  omitted_files: info",
        "  absolute_links: info",
        "  unrecognized_links: info",
        "  links:",
        "    not_found: info",
        "nav:",
    ]
    return "\n".join(head + yaml_nav(nav)) + "\n"


# ----------------------------------------------------------------------------------------------- diagramas.md
def build_diagramas_md(files: dict) -> str:
    md = [CABECERA_MD, "# Diagramas generados\n",
          "Todos se generan desde el código con `scripts/docs/gen_docs.py`. Los diagramas de casos de uso, actividad, secuencia, paquetes y arquitectura de `docs/diagramas/` "
          "se mantienen **a mano** y no se regeneran.\n"]
    titulos = [
        ("base_datos.mermaid", "Modelo entidad-relación de la base interna (SQLite)"),
        ("clases_modelos.mermaid", "Clases ORM (base interna)"),
        ("clases.mermaid", "Clases del motor, la seguridad y los servicios"),
        ("clases_schemas.mermaid", "Clases Pydantic de la API"),
        ("componentes.mermaid", "Componentes y dependencias entre paquetes"),
        ("despliegue.mermaid", "Despliegue (compose, Terraform y workflows)"),
    ]
    for fname, t in titulos:
        body = files["docs/diagramas/" + fname]
        body = "\n".join(l for l in body.splitlines() if not l.startswith("%% GENERADO"))
        md.append(f"## {t}\n\n```mermaid\n{body}\n```\n")
    return "\n".join(md)


# ----------------------------------------------------------------------------------------------- README
def count_tests():
    files = sorted((ROOT / "tests").glob("test_*.py"))
    n = 0
    for p in files:
        n += len(re.findall(r"^\s*(?:async\s+)?def (test_\w+)", p.read_text(encoding="utf-8"), re.M))
    return len(files), n


def cli_commands():
    from app import cli
    ap = cli.build_parser()
    for a in ap._actions:
        if a.__class__.__name__ == "_SubParsersAction":
            return sorted(a.choices)
    return []


def build_readme_block(rows, version, base) -> str:
    por_grupo = Counter(r[0] or "(sin grupo)" for r in rows)
    nfiles, ntests = count_tests()
    docs = []
    for p in sorted((ROOT / "docs").glob("*.md")):
        first = next((l[2:].strip() for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("# ")), p.stem)
        docs.append(f"- [{first}](docs/{p.name})")
    lines = [BEGIN, "<!-- Bloque generado por scripts/docs/gen_docs.py; no editar a mano. -->", "",
             f"**Versión de la API:** {version} · **Operaciones HTTP documentadas (OpenAPI):** {len(rows)} · **Tablas de la base interna (SQLite):** {len(base.metadata.tables)} · "
             f"**Archivos de prueba:** {nfiles} · **Funciones `test_` (recuento estático; no prueba que pasen):** {ntests}", "",
             "| Grupo de endpoints | Rutas |", "| --- | --- |"]
    for g, n in sorted(por_grupo.items()):
        lines.append(f"| {g} | {n} |")
    lines += ["", "**Tablas de la base interna:** " + ", ".join(f"`{t.name}`" for t in base.metadata.sorted_tables) + " (diccionario en [docs/generated/diccionario-datos.md](docs/generated/diccionario-datos.md)).", "",
              "**Subcomandos de la CLI** (`python -m app.cli`): " + ", ".join(f"`{c}`" for c in cli_commands()) + ".", "",
              "**Documentación del repositorio:**", ""] + docs + ["", END]
    return "\n".join(lines)


def apply_readme(current: str, block: str) -> str:
    if BEGIN in current and END in current:
        pre = current.split(BEGIN)[0]
        post = current.split(END, 1)[1]
        return pre + block + post
    return current.rstrip("\n") + "\n\n## Resumen generado\n\n" + block + "\n"


# ----------------------------------------------------------------------------------------------- cobertura de docstrings
def _class_properties(node: ast.ClassDef):
    """(nombre, documentada) de los atributos de clase y de los self.x de __init__. Documentada = tiene docstring de atributo."""
    props = {}
    body = node.body
    for i, item in enumerate(body):
        nombre = None
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            nombre = item.target.id
        elif isinstance(item, ast.Assign) and len(item.targets) == 1 and isinstance(item.targets[0], ast.Name):
            nombre = item.targets[0].id
        if nombre and not nombre.startswith("_"):
            sig = body[i + 1] if i + 1 < len(body) else None
            doc = isinstance(sig, ast.Expr) and isinstance(getattr(sig, "value", None), ast.Constant) and isinstance(sig.value.value, str)
            props[nombre] = doc
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            for sub in ast.walk(item):
                if isinstance(sub, ast.Assign):
                    for tg in sub.targets:
                        if isinstance(tg, ast.Attribute) and isinstance(tg.value, ast.Name) and tg.value.id == "self" and not tg.attr.startswith("_"):
                            props.setdefault(tg.attr, False)
    return props


def coverage_rows():
    """Una fila por módulo de app/: existentes vs documentados, y la lista de vacíos."""
    orm_cols = set(DESC.COLUMNAS)
    filas, vacios = [], []
    for p in app_modules():
        name = mod_name(p)
        tree = parse(p)
        r = {"mod": name, "mod_doc": bool(ast.get_docstring(tree)), "cls": [0, 0], "fn": [0, 0], "met": [0, 0], "prop": [0, 0], "prop_dic": 0}
        if not r["mod_doc"]:
            vacios.append((name, "módulo", name, 1))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                r["fn"][1] += 1
                if ast.get_docstring(node):
                    r["fn"][0] += 1
                else:
                    vacios.append((name, "función", node.name, node.lineno))
            elif isinstance(node, ast.ClassDef):
                r["cls"][1] += 1
                if ast.get_docstring(node):
                    r["cls"][0] += 1
                else:
                    vacios.append((name, "clase", node.name, node.lineno))
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and not item.name.startswith("_"):
                        r["met"][1] += 1
                        if ast.get_docstring(item):
                            r["met"][0] += 1
                        else:
                            vacios.append((name, "método", f"{node.name}.{item.name}", item.lineno))
                tabla = None
                for item in node.body:
                    if isinstance(item, ast.Assign) and len(item.targets) == 1 and getattr(item.targets[0], "id", "") == "__tablename__":
                        tabla = item.value.value
                for pn, doc in sorted(_class_properties(node).items()):
                    r["prop"][1] += 1
                    en_dic = bool(tabla and f"{tabla}.{pn}" in orm_cols)
                    if doc:
                        r["prop"][0] += 1
                    elif en_dic:
                        r["prop_dic"] += 1
                    else:
                        vacios.append((name, "propiedad", f"{node.name}.{pn}", 0))
        filas.append(r)
    return filas, vacios


def build_doc_coverage() -> str:
    filas, vacios = coverage_rows()
    md = [CABECERA_MD, "# Cobertura de documentación del código (`app/`)" + NL,
          "Cuenta lo que existe en cada módulo y cuánto tiene docstring. **Documentada** significa: la clase, función o método tiene docstring; "
          "una propiedad (atributo de clase, campo, `self.x` de `__init__`) la tiene si lleva un docstring de atributo o, solo en las columnas del modelo ORM, "
          "si figura en el diccionario de datos (`scripts/docs/descripciones_datos.py`, columna «Propiedades en diccionario»). Se excluyen nombres que empiezan por `_`. "
          "Es una medida **formal** (existe texto), no de calidad del texto." + NL,
          "| Módulo | Docstring del módulo | Clases (doc/total) | Funciones (doc/total) | Métodos (doc/total) | Propiedades con docstring (doc/total) | Propiedades en diccionario | Propiedades sin describir |",
          "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    tot = {"cls": [0, 0], "fn": [0, 0], "met": [0, 0], "prop": [0, 0], "dic": 0, "mod": [0, 0]}
    for r in filas:
        sin = r["prop"][1] - r["prop"][0] - r["prop_dic"]
        md.append("| `{}` | {} | {}/{} | {}/{} | {}/{} | {}/{} | {} | {} |".format(
            r["mod"], "sí" if r["mod_doc"] else "**no**", r["cls"][0], r["cls"][1], r["fn"][0], r["fn"][1], r["met"][0], r["met"][1],
            r["prop"][0], r["prop"][1], r["prop_dic"], sin))
        for k in ("cls", "fn", "met", "prop"):
            tot[k][0] += r[k][0]
            tot[k][1] += r[k][1]
        tot["dic"] += r["prop_dic"]
        tot["mod"][0] += 1 if r["mod_doc"] else 0
        tot["mod"][1] += 1
    sin_total = tot["prop"][1] - tot["prop"][0] - tot["dic"]
    md.append("| **Total** | {}/{} | {}/{} | {}/{} | {}/{} | {}/{} | {} | {} |".format(
        tot["mod"][0], tot["mod"][1], tot["cls"][0], tot["cls"][1], tot["fn"][0], tot["fn"][1], tot["met"][0], tot["met"][1],
        tot["prop"][0], tot["prop"][1], tot["dic"], sin_total))
    md.append("")
    md.append("## Vacíos (sin docstring)" + NL)
    por_tipo = defaultdict(list)
    for mod, tipo, nombre, linea in vacios:
        por_tipo[tipo].append((mod, nombre, linea))
    if not vacios:
        md.append("Ninguno.")
    for tipo in ("módulo", "clase", "función", "método", "propiedad"):
        items = por_tipo.get(tipo, [])
        if not items:
            continue
        plural = {"módulo": "Módulos", "clase": "Clases", "función": "Funciones", "método": "Métodos", "propiedad": "Propiedades"}[tipo]
        md.append(f"### {plural} sin documentar ({len(items)})" + NL)
        if tipo == "propiedad":
            agrupado = defaultdict(list)
            for mod, nombre, _ in items:
                cls, prop = nombre.split(".", 1)
                agrupado[(mod, cls)].append(prop)
            md.append("| Módulo | Clase | Propiedades |" + NL + "| --- | --- | --- |")
            for (mod, cls), props in sorted(agrupado.items()):
                md.append(f"| `{mod}` | `{cls}` | {', '.join('`' + x + '`' for x in props)} |")
        else:
            md.append("| Módulo | Nombre | Línea |" + NL + "| --- | --- | --- |")
            for mod, nombre, linea in items:
                md.append(f"| `{mod}` | `{nombre}` | {linea if linea else ''} |")
        md.append("")
    return NL.join(md).rstrip() + NL


# ----------------------------------------------------------------------------------------------- orquestación
def compute_all():
    base = load_metadata()
    check_descriptions(base)
    out = {}
    out["docs/generated/diccionario-datos.md"] = build_dictionary(base)
    out["docs/diagramas/base_datos.mermaid"] = build_er(base)
    out.update({"docs/diagramas/" + k: v for k, v in build_class_diagrams().items()})
    out["docs/diagramas/componentes.mermaid"] = build_components()
    out["docs/diagramas/despliegue.mermaid"] = build_deployment()
    ep_md, rows, version = build_endpoints()
    out["docs/generated/api-endpoints.md"] = ep_md
    out["docs/generated/cobertura-docstrings.md"] = build_doc_coverage()
    out["docs/generated/diagramas.md"] = build_diagramas_md(out)
    pages, ref_nav = build_reference_pages()
    out.update(pages)
    out["mkdocs.yml"] = build_mkdocs(ref_nav)
    readme_path = ROOT / "README.md"
    out["README.md"] = apply_readme(readme_path.read_text(encoding="utf-8"), build_readme_block(rows, version, base))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="no escribe; falla si algo generado está desactualizado")
    args = ap.parse_args(argv)
    # Como script solo se importan los modelos y la app: crea el motor de SQLAlchemy, no archivos.
    # La URL en memoria evita tocar una base real. (No se hace al importar el módulo desde pytest.)
    os.environ["FRAMEWORK_DB_URL"] = "sqlite://"
    os.environ.pop("APP_ACCESS_ENABLED", None)
    out = compute_all()
    stale = []
    for relpath, content in sorted(out.items()):
        path = ROOT / relpath
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != content:
            stale.append(relpath)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8", newline="\n")
    # Referencia: borra páginas de módulos que ya no existen
    ref_dir = ROOT / "docs" / "referencia"
    previstos = {ROOT / k for k in out if k.startswith("docs/referencia/")}
    for p in sorted(ref_dir.glob("*.md")) if ref_dir.exists() else []:
        if p not in previstos:
            stale.append(rel(p) + " (sobra)")
            if not args.check:
                p.unlink()
    if args.check:
        if stale:
            print("DESACTUALIZADO: " + ", ".join(stale))
            print("Ejecute: python scripts/docs/gen_docs.py")
            return 1
        print(f"OK: {len(out)} archivos generados al día.")
        return 0
    print(f"Generados {len(out)} archivos; actualizados: {len(stale)}")
    for s in stale:
        print("  -", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
