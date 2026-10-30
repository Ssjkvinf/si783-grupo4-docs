#!/usr/bin/env python3
"""
Restaura una copia de la SQLite en una ubicación AISLADA y verifica que se puede leer.

Garantías de seguridad (por diseño):
  - Nunca escribe sobre la base activa: si --active-db se indica y el destino coincide, se rechaza.
  - Restaura solo dentro de --work-dir, que debe ser una carpeta nueva o vacía.
  - Antes de restaurar comprueba el SHA-256 de la copia contra el manifiesto.

Verificaciones: hash del archivo, integrity_check, foreign_key_check, filas por tabla = las del manifiesto
y lectura de datos reales de las tablas principales (proyectos, conexiones, casos, suites, historial).

Uso:
  python sqlite_restore_verify.py --backup copia.sqlite.gz --manifest copia.manifest.json \
      --work-dir /tmp/restauracion [--active-db /data/framework_interno.db]

Código de salida: 0 restauración verificada; 1 verificación fallida; 2 argumentos o ubicación inválidos.
"""
import argparse
import gzip
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sqlite_backup import inspect_database, sha256_of  # noqa: E402

MAIN_TABLES = ["projects", "connection_profiles", "test_cases", "test_suites", "execution_history"]


class RestoreError(Exception):
    pass


def read_samples(db: Path) -> Dict[str, Any]:
    """Lee datos reales de la copia restaurada: conteos y nombres (no contraseñas: no se guardan en esta base)."""
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        out: Dict[str, Any] = {}
        existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for t in MAIN_TABLES:
            if t in existing:
                out[t] = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if "projects" in existing:
            out["proyectos_ejemplo"] = [r[0] for r in conn.execute("SELECT name FROM projects ORDER BY id LIMIT 3")]
        if "execution_history" in existing:
            row = conn.execute("SELECT id, status, executed_at FROM execution_history ORDER BY id DESC LIMIT 1").fetchone()
            out["ultima_ejecucion"] = list(row) if row else None
        return out
    finally:
        conn.close()


def restore(backup: Path, manifest: Dict[str, Any], work_dir: Path, active_db: Optional[Path]) -> Dict[str, Any]:
    if not backup.is_file():
        raise RestoreError(f"No existe la copia: {backup}")
    if work_dir.exists() and any(work_dir.iterdir()):
        raise RestoreError(f"La carpeta de restauración {work_dir} no está vacía; use una carpeta nueva.")
    work_dir.mkdir(parents=True, exist_ok=True)
    target = work_dir / "restaurada.sqlite"
    if active_db is not None and target.resolve() == active_db.resolve():
        raise RestoreError("El destino de la restauración coincide con la base activa: rechazado.")

    checks: List[Dict[str, Any]] = []

    def check(nombre: str, ok: bool, detalle: str = ""):
        checks.append({"comprobacion": nombre, "ok": bool(ok), "detalle": detalle})

    # 1. Hash del archivo contra el manifiesto
    actual = sha256_of(backup)
    check("SHA-256 del archivo coincide con el manifiesto", actual == manifest["sha256"], f"esperado {manifest['sha256'][:16]}…, actual {actual[:16]}…")
    if actual != manifest["sha256"]:
        return {"ok": False, "checks": checks, "restaurada": None, "muestras": None}

    # 2. Restauración aislada
    if backup.suffix == ".gz":
        with gzip.open(backup, "rb") as f_in, target.open("wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copyfile(backup, target)
    check("SHA-256 de la base restaurada coincide con la original", sha256_of(target) == manifest["sha256_sin_comprimir"])

    # 3. Integridad y contenido
    info = inspect_database(target)
    check("PRAGMA integrity_check = ok", info["integrity_ok"], ", ".join(info["integrity_check"]))
    check("Sin violaciones de claves foráneas", info["foreign_key_violations"] == 0, str(info["foreign_key_violations"]))
    check("Filas por tabla = las del manifiesto", info["filas_por_tabla"] == manifest["filas_por_tabla"])
    check("Versión de migración (Alembic) = la del manifiesto", info["alembic_version"] == manifest["alembic_version"], str(info["alembic_version"]))

    muestras = read_samples(target)
    check("Se pueden leer datos de las tablas principales", len([t for t in MAIN_TABLES if t in muestras]) >= 1, json.dumps({k: v for k, v in muestras.items() if k in MAIN_TABLES}))
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "restaurada": target.as_posix(), "muestras": muestras}


def render_markdown(manifest: Dict[str, Any], res: Dict[str, Any], work_dir: Path) -> str:
    rows = "\n".join(f"| {c['comprobacion']} | {'✔' if c['ok'] else '✘ FALLA'} | {c['detalle']} |" for c in res["checks"])
    m = res.get("muestras") or {}
    ejemplo = f"\nProyectos leídos de la copia restaurada: {', '.join(m.get('proyectos_ejemplo', [])) or '(ninguno)'}\n" if m else ""
    return f"""# Reporte de restauración verificada

**Resultado: {'RESTAURACIÓN VERIFICADA' if res['ok'] else 'FALLÓ LA VERIFICACIÓN'}**

- Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
- Copia: `{manifest['archivo']}` (creada {manifest['fecha_utc']})
- Restaurada en una carpeta aislada: `{work_dir.as_posix()}` — **la base activa no se tocó**

| Comprobación | Resultado | Detalle |
| --- | --- | --- |
{rows}
{ejemplo}
> Esta verificación se hizo sobre una copia en una carpeta aislada. Reemplazar la base activa de la aplicación es un paso aparte,
> manual y con la API detenida (ver docs/operacion-fase3.md).
"""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--backup", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--work-dir", required=True, type=Path)
    ap.add_argument("--active-db", type=Path, default=None, help="ruta de la base activa (solo para rechazar si coincidiera)")
    ap.add_argument("--report", type=Path, default=None, help="archivo del reporte Markdown (por defecto junto a --work-dir)")
    args = ap.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        res = restore(args.backup, manifest, args.work_dir, args.active_db)
    except (RestoreError, OSError, json.JSONDecodeError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, (RestoreError, OSError, json.JSONDecodeError)) else 1

    md = render_markdown(manifest, res, args.work_dir)
    report = args.report or args.work_dir.with_suffix(".reporte-restauracion.md")
    report.write_text(md, encoding="utf-8")
    (report.with_suffix(".json")).write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    sys.stdout.write(md)
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
