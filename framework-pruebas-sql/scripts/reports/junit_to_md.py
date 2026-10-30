#!/usr/bin/env python3
"""
Convierte un informe JUnit (pytest --junitxml) en un resumen Markdown.

Distingue PASADAS, FALLADAS, con ERROR y OMITIDAS: una prueba omitida NO cuenta como aprobada.
Uso: python junit_to_md.py --junit pytest.xml --out pruebas.md --title "Pruebas de la aplicación"
Código de salida: 1 si hay fallos o errores; 0 en otro caso.
"""
import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional


def summarize(path: Path):
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = failures = errors = skipped = 0
    seconds = 0.0
    failed: List[str] = []
    skipped_list: List[str] = []
    for s in suites:
        total += int(s.get("tests", 0))
        failures += int(s.get("failures", 0))
        errors += int(s.get("errors", 0))
        skipped += int(s.get("skipped", 0))
        seconds += float(s.get("time", 0) or 0)
        for case in s.iter("testcase"):
            name = f"{case.get('classname', '')}::{case.get('name', '')}"
            if case.find("failure") is not None or case.find("error") is not None:
                failed.append(name)
            elif case.find("skipped") is not None:
                skipped_list.append(name)
    passed = total - failures - errors - skipped
    return {"total": total, "passed": passed, "failures": failures, "errors": errors, "skipped": skipped,
            "seconds": seconds, "failed": failed, "skipped_list": skipped_list}


def render(r, title: str) -> str:
    out = [f"# {title}", ""]
    out.append("| Total | Pasadas | Falladas | Con error | Omitidas | Tiempo (s) |")
    out.append("| ---: | ---: | ---: | ---: | ---: | ---: |")
    out.append(f"| {r['total']} | **{r['passed']}** | {r['failures']} | {r['errors']} | {r['skipped']} | {r['seconds']:.1f} |")
    out.append("")
    out.append("Las pruebas **omitidas no se cuentan como aprobadas**.")
    if r["failed"]:
        out += ["", "## Pruebas que fallaron", ""] + [f"- `{n}`" for n in r["failed"]]
    if r["skipped_list"]:
        out += ["", f"## Pruebas omitidas ({len(r['skipped_list'])})", ""] + [f"- `{n}`" for n in r["skipped_list"][:30]]
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--junit", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--title", default="Reporte de pruebas")
    args = ap.parse_args(argv)
    r = summarize(args.junit)
    md = render(r, args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 1 if (r["failures"] or r["errors"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
