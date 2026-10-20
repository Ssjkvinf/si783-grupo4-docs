#!/usr/bin/env python3
"""
Reporte de migraciones Alembic sobre una SQLite DESECHABLE (la base interna de la aplicación).

Aplica `alembic upgrade head` DOS veces sobre un archivo nuevo y comprueba:
  - la 1.ª ejecución crea el esquema; la 2.ª no aplica ninguna migración (idempotencia);
  - la revisión final (`alembic current`) es la cabeza;
  - integridad y claves foráneas de la base resultante;
  - `alembic check` (¿los modelos del código coinciden con las migraciones?) — informativo.

Nunca toca la base activa: trabaja en una carpeta temporal (o la que se indique en --db).

Uso: python sqlite_migrations_report.py --out reporte.md [--json reporte.json] [--db archivo_nuevo.sqlite]
Código de salida: 0 si todo correcto; 1 si falla la idempotencia o la integridad.
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def alembic(db: Path, *args: str) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["FRAMEWORK_DB_URL"] = f"sqlite:///{db.as_posix()}"
    env.pop("APP_SESSION_SECRET", None)
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=PROJECT_ROOT, env=env,
                          capture_output=True, text=True, timeout=300)


def applied(output: str) -> List[str]:
    return [ln.split("Running upgrade", 1)[1].strip() for ln in output.splitlines() if "Running upgrade" in ln]


def schema_of(db: Path) -> Dict[str, Any]:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        tables = {}
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
            cols = [f"{c[1]} {c[2]}" + (" PK" if c[5] else "") + (" NOT NULL" if c[3] else "") for c in conn.execute(f'PRAGMA table_info("{name}")')]
            tables[name] = cols
        integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        return {"tablas": tables, "integrity": integrity, "fk_violaciones": len(fk), "version": version[0] if version else None}
    finally:
        conn.close()


def run(db: Path) -> Dict[str, Any]:
    r1 = alembic(db, "upgrade", "head")
    r2 = alembic(db, "upgrade", "head")
    cur = alembic(db, "current")
    heads = alembic(db, "heads")
    chk = alembic(db, "check")
    schema = schema_of(db) if db.exists() and r1.returncode == 0 else {}
    head_rev = (heads.stdout.split() or [""])[0]
    current_rev = (cur.stdout.split() or [""])[0]
    result = {
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "primera": {"ok": r1.returncode == 0, "migraciones_aplicadas": applied(r1.stderr + r1.stdout)},
        "segunda": {"ok": r2.returncode == 0, "migraciones_aplicadas": applied(r2.stderr + r2.stdout)},
        "revision_actual": current_rev, "revision_cabeza": head_rev,
        "esquema": schema,
        "alembic_check": {"codigo": chk.returncode, "salida": (chk.stdout + chk.stderr).strip()[-1500:]},
    }
    result["idempotente"] = bool(result["primera"]["ok"] and result["segunda"]["ok"] and not result["segunda"]["migraciones_aplicadas"])
    result["ok"] = bool(result["idempotente"] and current_rev == head_rev and schema
                        and schema.get("integrity") == ["ok"] and schema.get("fk_violaciones") == 0)
    return result


def render(r: Dict[str, Any]) -> str:
    esq = r["esquema"] or {}
    filas = "\n".join(f"| `{t}` | {', '.join(cols)} |" for t, cols in (esq.get("tablas") or {}).items())
    drift = "sin diferencias" if r["alembic_check"]["codigo"] == 0 else "HAY DIFERENCIAS (ver abajo)"
    return f"""# Reporte de migraciones de la SQLite interna (Alembic)

**Resultado: {'CORRECTO' if r['ok'] else 'FALLA'}** — {r['fecha_utc']}

Alcance: **SQLite interna** de la aplicación (proyectos, conexiones, casos, suites, historial), versionada con **Alembic** (`alembic/`).
Los objetos de **Oracle** de la demostración se versionan con Liquibase (otro reporte). Se trabajó sobre un archivo SQLite nuevo y desechable.

| Comprobación | Resultado |
| --- | --- |
| 1.ª ejecución de `alembic upgrade head` | {'correcta' if r['primera']['ok'] else 'FALLÓ'}: {len(r['primera']['migraciones_aplicadas'])} migraciones aplicadas |
| 2.ª ejecución | {'correcta' if r['segunda']['ok'] else 'FALLÓ'}: **{len(r['segunda']['migraciones_aplicadas'])} migraciones aplicadas** (debe ser 0) |
| Idempotencia | **{'CORRECTA' if r['idempotente'] else 'FALLA'}** |
| Revisión actual = cabeza | {r['revision_actual']} = {r['revision_cabeza']} |
| `PRAGMA integrity_check` | {', '.join(esq.get('integrity', [])) or 'no ejecutado'} |
| Violaciones de claves foráneas | {esq.get('fk_violaciones')} |
| `alembic check` (modelos vs. migraciones) | {drift} |

## Migraciones aplicadas en la 1.ª ejecución

{chr(10).join('- ' + m for m in r['primera']['migraciones_aplicadas']) or '(ninguna)'}

## Esquema resultante

| Tabla | Columnas |
| --- | --- |
{filas}

{'## Salida de `alembic check`' + chr(10) + chr(10) + '```' + chr(10) + r['alembic_check']['salida'] + chr(10) + '```' if r['alembic_check']['codigo'] != 0 else ''}
"""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--db", type=Path, default=None, help="archivo SQLite NUEVO a usar (por defecto uno temporal)")
    args = ap.parse_args(argv)

    if args.db:
        if args.db.exists():
            print("ERROR: --db debe ser un archivo que no exista (no se migra una base existente).", file=sys.stderr)
            return 2
        result = run(args.db)
    else:
        with tempfile.TemporaryDirectory() as tmp:
            result = run(Path(tmp) / "migraciones_prueba.sqlite")

    md = render(result)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.stdout.write(md)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
