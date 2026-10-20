#!/usr/bin/env python3
"""
Genera checks/reglas_demo.xlsx: las reglas de calidad de la demostración en formato de importación (Excel).

Es la FUENTE VERSIONADA de las comprobaciones que ejecuta el flujo sql-checks.yml: el archivo se revisa en las
Pull Requests como cualquier código. Sale de app/services/demo_scenario.py (una sola definición de las reglas);
una prueba automática comprueba que el archivo del repositorio coincide con lo que genera este script.

Uso: python scripts/checks/generate_demo_checks.py [salida.xlsx]
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services import demo_scenario, excel_io  # noqa: E402

SUITE_NAME = "Reglas de calidad (demo)"


def demo_rows():
    return [(name, desc, sql, val, exp, SUITE_NAME) for name, desc, sql, val, exp in demo_scenario.RULES_CASES]


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    out = Path(argv[0]) if argv else ROOT / "checks" / "reglas_demo.xlsx"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(excel_io.build_cases_file(demo_rows()))
    print(f"Generado {out} con {len(demo_scenario.RULES_CASES)} reglas (suite «{SUITE_NAME}»)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
