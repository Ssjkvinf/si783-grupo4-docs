#!/usr/bin/env python3
"""
Reporte de ejecuciones de Liquibase sobre Oracle (entrada: carpeta con los registros de liquibase_demo.sh).

Comprueba la IDEMPOTENCIA: la segunda ejecución de `update` no debe aplicar ningún changeset.
Código de salida: 0 si la 1.ª ejecución terminó bien y la 2.ª aplicó 0 cambios; 1 en otro caso.

Uso: python liquibase_report.py --logs carpeta --out reporte.md --entorno "texto" [--objects objetos.txt]
"""
import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def parse_update(text: str) -> Dict[str, Optional[int]]:
    def num(label: str) -> Optional[int]:
        m = re.search(rf"{label}:\s+(\d+)", text)
        return int(m.group(1)) if m else None

    return {
        "ejecutados": num("Run"),
        "ya_ejecutados": num("Previously run"),
        "filtrados": num("Filtered out"),
        "total": num("Total change sets"),
        "ok": "was executed successfully" in text,
    }


def marked_ran(text: str) -> List[str]:
    out = []
    # Formato real de Liquibase 4.33: Marking ChangeSet: "ruta::id::autor" as ran despite precondition failure due to onFail='MARK_RAN'
    for m in re.finditer(r'Marking ChangeSet:\s*"?([^"\s]+)"?\s+as ran despite precondition failure', text):
        out.append(m.group(1))
    return out


def render(logs: Path, entorno: str, objects: Optional[str]) -> (str, bool):
    r1 = parse_update(read(logs / "01_update_1.log"))
    r2 = parse_update(read(logs / "02_update_2.log"))
    validate_ok = "validated successfully" in read(logs / "00_validate.log") or "No validation errors" in read(logs / "00_validate.log")
    marked = marked_ran(read(logs / "01_update_1.log"))
    idempotent = bool(r1["ok"]) and bool(r2["ok"]) and r2["ejecutados"] == 0
    version = re.search(r"Liquibase Version:\s*(\S+)", read(logs / "01_update_1.log"))

    m = ["# Reporte de ejecuciones de Liquibase (objetos Oracle)", ""]
    m.append(f"- Fecha: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    m.append(f"- Entorno: {entorno}")
    m.append(f"- Versión de Liquibase: {version.group(1) if version else 'no detectada'}")
    m.append("- Alcance: objetos **Oracle** de la demostración (esquema FRAMEWORK_TEST). La SQLite interna la versiona Alembic (otro reporte).")
    m.append("")
    m.append("## Resultado")
    m.append("")
    m.append("| Comprobación | Resultado |")
    m.append("| --- | --- |")
    m.append(f"| Validación de los changelogs | {'correcta' if validate_ok else 'no confirmada'} |")
    m.append(f"| 1.ª ejecución de `update` | {'correcta' if r1['ok'] else 'FALLÓ'} |")
    m.append(f"| 2.ª ejecución de `update` | {'correcta' if r2['ok'] else 'FALLÓ'} |")
    m.append(f"| **Idempotencia** (la 2.ª no aplica cambios) | **{'CORRECTA' if idempotent else 'FALLA'}** |")
    m.append("")
    m.append("| Ejecución | Changesets aplicados | Ya ejecutados antes | Filtrados por contexto | Total |")
    m.append("| --- | ---: | ---: | ---: | ---: |")
    for nombre, r in (("1.ª", r1), ("2.ª", r2)):
        m.append(f"| {nombre} | {r['ejecutados']} | {r['ya_ejecutados']} | {r['filtrados']} | {r['total']} |")
    m.append("")
    if marked:
        m.append("## Changesets marcados como ejecutados sin aplicarse (el objeto ya existía)")
        m.append("")
        m += [f"- `{c}`" for c in marked]
        m.append("")
    hist = read(logs / "03_history.log").strip()
    if hist:
        m += ["## Historial (DATABASECHANGELOG)", "", "```", hist[-3500:], "```", ""]
    if objects:
        m += ["## Objetos del esquema después de la ejecución", "", "```", objects.strip()[:3500], "```", ""]
    m.append("## Límites")
    m.append("")
    m.append("- Se comprobó con un Oracle desechable; esto no certifica el comportamiento en otras versiones ni en la VM de Azure.")
    m.append("- El contexto `demo` borra y recarga los datos de `FRAMEWORK_TEST_ITEMS`: no usarlo en una base con datos reales.")
    return "\n".join(m) + "\n", idempotent


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--logs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--entorno", default="Oracle desechable")
    ap.add_argument("--objects", type=Path, default=None)
    args = ap.parse_args(argv)
    md, ok = render(args.logs, args.entorno, read(args.objects) if args.objects else None)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
