#!/usr/bin/env python3
"""
Copia de seguridad CONSISTENTE de la SQLite interna (proyectos, conexiones, casos, suites, historial).

Por qué no basta copiar el archivo: mientras la aplicación escribe, un `cp` puede capturar páginas de
transacciones distintas y producir una copia corrupta. Aquí se usa la API de respaldo en línea de SQLite
(`sqlite3.Connection.backup`), que toma una instantánea coherente aunque haya escrituras en curso.

Qué hace:
  1. Abre el origen en SOLO LECTURA (no lo modifica).
  2. Copia con la API de respaldo a un archivo nuevo (nunca sobre el origen).
  3. Comprueba la copia: PRAGMA integrity_check, PRAGMA foreign_key_check y filas por tabla.
  4. (Opcional) comprime, y calcula SHA-256 y tamaño.
  5. Escribe un manifiesto JSON y un reporte Markdown (sin contenido de las tablas; solo conteos).

Uso:
  python sqlite_backup.py --db /data/framework_interno.db --out-dir /backup [--gzip] [--prefix framework_interno]

Código de salida: 0 correcto; 1 si la copia no pasa la comprobación; 2 si los argumentos son inválidos.
"""
import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def sha256_of(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    names = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in names}


def inspect_database(path: Path) -> Dict[str, Any]:
    """Comprueba una base SQLite abriéndola en solo lectura."""
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        integrity = [r[0] for r in conn.execute("PRAGMA integrity_check")]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        counts = table_counts(conn)
        version = None
        if "alembic_version" in counts:
            row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            version = row[0] if row else None
        return {"integrity_check": integrity, "integrity_ok": integrity == ["ok"],
                "foreign_key_violations": len(fk), "filas_por_tabla": counts, "alembic_version": version}
    finally:
        conn.close()


def make_backup(db: Path, out_dir: Path, prefix: str, compress: bool) -> Dict[str, Any]:
    if not db.is_file():
        raise FileNotFoundError(f"No existe la base de origen: {db}")
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_dir.resolve() == db.resolve().parent:
        # Una copia junto a la base activa se perdería con ella (mismo disco/volumen) y ensucia su carpeta.
        raise ValueError("La carpeta de destino no debe ser la carpeta de la base activa.")

    started = time.time()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_name = f"{prefix}_{stamp}.sqlite"
    raw_path = out_dir / raw_name
    if raw_path.resolve() == db.resolve():
        raise ValueError("El destino no puede ser el mismo archivo que el origen.")
    if raw_path.exists():
        raise FileExistsError(f"Ya existe {raw_path}; no se sobrescribe una copia.")

    # 1-2. Instantánea coherente con la API de respaldo (el origen se abre en solo lectura)
    src = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True, timeout=30)
    dst = sqlite3.connect(raw_path.as_posix())
    try:
        src.backup(dst)           # todas las páginas en una sola instantánea
    finally:
        dst.close()
        src.close()

    # 3. Comprobación de la copia
    check = inspect_database(raw_path)
    raw_size = raw_path.stat().st_size
    raw_hash = sha256_of(raw_path)

    final_path = raw_path
    gz_hash = None
    if compress:
        final_path = out_dir / (raw_name + ".gz")
        with raw_path.open("rb") as f_in, gzip.open(final_path, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
        raw_path.unlink()          # se conserva solo la comprimida; el hash de la base sin comprimir queda en el manifiesto
        gz_hash = sha256_of(final_path)

    manifest: Dict[str, Any] = {
        "tipo": "copia_sqlite_consistente",
        "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "metodo": "sqlite3.Connection.backup (API de respaldo en línea; origen abierto en solo lectura)",
        "origen": db.as_posix(),
        "archivo": final_path.name,
        "comprimido": compress,
        "tamano_bytes": final_path.stat().st_size,
        "sha256": gz_hash if compress else raw_hash,
        "tamano_bytes_sin_comprimir": raw_size,
        "sha256_sin_comprimir": raw_hash,
        "integrity_check": check["integrity_check"],
        "integrity_ok": check["integrity_ok"],
        "foreign_key_violations": check["foreign_key_violations"],
        "filas_por_tabla": check["filas_por_tabla"],
        "alembic_version": check["alembic_version"],
        "duracion_s": round(time.time() - started, 3),
    }
    manifest["ok"] = bool(check["integrity_ok"] and check["foreign_key_violations"] == 0)
    return manifest


def render_markdown(m: Dict[str, Any]) -> str:
    rows = "\n".join(f"| `{t}` | {n} |" for t, n in m["filas_por_tabla"].items())
    veredicto = "CORRECTA" if m["ok"] else "FALLÓ LA COMPROBACIÓN"
    return f"""# Reporte de copia de seguridad de la SQLite

**Resultado: {veredicto}**

| Dato | Valor |
| --- | --- |
| Fecha | {m['fecha_utc']} |
| Método | {m['metodo']} |
| Origen | `{m['origen']}` |
| Archivo de la copia | `{m['archivo']}` |
| Tamaño | {m['tamano_bytes']} bytes |
| SHA-256 del archivo | `{m['sha256']}` |
| SHA-256 de la base sin comprimir | `{m['sha256_sin_comprimir']}` |
| `PRAGMA integrity_check` | {', '.join(m['integrity_check'])} |
| Violaciones de claves foráneas | {m['foreign_key_violations']} |
| Versión de migración (Alembic) | {m['alembic_version']} |
| Duración | {m['duracion_s']} s |

## Filas por tabla (solo conteos; el reporte no contiene datos)

| Tabla | Filas |
| --- | ---: |
{rows}

> La copia se hizo con la API de respaldo de SQLite, no copiando el archivo en uso. Una copia solo es válida tras **restaurarla y leerla**
> (`sqlite_restore_verify.py`): este reporte demuestra la integridad de la copia, no la restauración.
"""


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, type=Path, help="SQLite de origen (no se modifica)")
    ap.add_argument("--out-dir", required=True, type=Path, help="carpeta de destino de la copia y los reportes")
    ap.add_argument("--prefix", default="framework_interno")
    ap.add_argument("--gzip", action="store_true", help="comprimir la copia")
    args = ap.parse_args(argv)
    try:
        manifest = make_backup(args.db, args.out_dir, args.prefix, args.gzip)
    except (FileNotFoundError, FileExistsError, ValueError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2 if isinstance(exc, (FileNotFoundError, FileExistsError, ValueError)) else 1

    base = args.out_dir / manifest["archivo"].replace(".sqlite.gz", "").replace(".sqlite", "")
    (Path(str(base) + ".manifest.json")).write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    md = render_markdown(manifest)
    (Path(str(base) + ".reporte.md")).write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
