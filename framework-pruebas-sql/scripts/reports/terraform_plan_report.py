#!/usr/bin/env python3
"""
Resumen legible de un plan de Terraform (entrada: `terraform show -json tfplan`).

Sirve de control de seguridad antes de aplicar cambios:
  - cuenta lo que se crea, cambia y elimina;
  - BLOQUEA (código de salida 2) si el plan elimina o reemplaza algo, si modifica una VM o cualquier recurso que la
    acompaña (disco, tarjeta de red, IP pública, NSG, red, extensiones, grupo de recursos), o si trae una acción que
    este script no conoce (p. ej. «forget»): una VM existente nunca debe cambiar por este flujo;
  - deja claro cuándo no hay cambios.

Uso: python terraform_plan_report.py --plan tfplan.json --out plan_report.md [--fmt ok|fallo] [--validate ok|fallo]
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

VM_TYPES = {"azurerm_linux_virtual_machine", "azurerm_windows_virtual_machine", "azurerm_virtual_machine"}
# Recursos de los que depende una VM en marcha: en este flujo solo pueden CREARSE (modo VM nueva), nunca modificarse ni borrarse.
VM_RELATED_TYPES = VM_TYPES | {
    "azurerm_resource_group", "azurerm_managed_disk", "azurerm_virtual_machine_data_disk_attachment",
    "azurerm_network_interface", "azurerm_public_ip", "azurerm_network_security_group", "azurerm_network_security_rule",
    "azurerm_virtual_network", "azurerm_subnet", "azurerm_subnet_network_security_group_association",
    "azurerm_network_interface_security_group_association", "azurerm_virtual_machine_extension",
}
KNOWN_ACTIONS = {"no-op", "read", "create", "update", "delete"}


def classify(actions: List[str]) -> str:
    if actions == ["no-op"] or actions == ["read"]:
        return "sin cambios"
    if "delete" in actions and "create" in actions:
        return "REEMPLAZO"
    if "delete" in actions:
        return "ELIMINACIÓN"
    if "create" in actions:
        return "creación"
    if "update" in actions:
        return "modificación"
    return "/".join(actions)


def analyze(plan: Dict[str, Any]) -> Dict[str, Any]:
    rows: List[Tuple[str, str, str]] = []
    problems: List[str] = []
    for rc in plan.get("resource_changes", []):
        label = classify(rc["change"]["actions"])
        rows.append((rc["address"], rc["type"], label))
        if label in ("REEMPLAZO", "ELIMINACIÓN"):
            problems.append(f"`{rc['address']}`: {label}")
        actions = rc["change"]["actions"]
        if rc["type"] in VM_RELATED_TYPES and label not in ("sin cambios", "creación", "REEMPLAZO", "ELIMINACIÓN"):
            problems.append(f"`{rc['address']}`: cambia la VM o un recurso del que depende ({label})")
        desconocidas = [a for a in actions if a not in KNOWN_ACTIONS]
        if desconocidas:
            problems.append(f"`{rc['address']}`: acción no reconocida ({'/'.join(desconocidas)}); revise el plan a mano")
    counts = Counter(r[2] for r in rows)
    return {"rows": rows, "counts": counts, "problems": problems}


def render(result: Dict[str, Any], fmt: str, validate: str, plan_name: str) -> str:
    c = result["counts"]
    out = ["# Reporte del plan de Terraform", ""]
    out.append(f"Plan analizado: `{plan_name}`")
    out.append("")
    out.append("## Comprobaciones")
    out.append("")
    out.append("| Comprobación | Resultado |")
    out.append("| --- | --- |")
    out.append(f"| `terraform fmt -check` | {fmt} |")
    out.append(f"| `terraform validate` | {validate} |")
    out.append(f"| Plan sin eliminaciones ni reemplazos | {'FALLA' if result['problems'] else 'correcto'} |")
    out.append("")
    out.append("## Resumen de cambios")
    out.append("")
    out.append(f"- Creaciones: **{c.get('creación', 0)}**")
    out.append(f"- Modificaciones: **{c.get('modificación', 0)}**")
    out.append(f"- Eliminaciones: **{c.get('ELIMINACIÓN', 0)}**")
    out.append(f"- Reemplazos: **{c.get('REEMPLAZO', 0)}**")
    out.append(f"- Sin cambios: {c.get('sin cambios', 0)}")
    if not any(v for k, v in c.items() if k != "sin cambios"):
        out.append("")
        out.append("**No hay cambios de infraestructura en este plan.**")
    out.append("")
    if result["rows"]:
        out.append("| Recurso | Tipo | Acción |")
        out.append("| --- | --- | --- |")
        for addr, typ, label in result["rows"]:
            out.append(f"| `{addr}` | `{typ}` | {label} |")
        out.append("")
    if result["problems"]:
        out.append("## ⛔ Plan BLOQUEADO para aplicar")
        out.append("")
        for p in result["problems"]:
            out.append(f"- {p}")
        out.append("")
        out.append("Este flujo no elimina ni reemplaza recursos y no modifica la VM existente. Revise las variables antes de continuar.")
    else:
        out.append("Plan apto para revisión humana. Revise la tabla anterior y el reporte de costos antes de aprobar el `apply`.")
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--fmt", default="no ejecutado")
    ap.add_argument("--validate", default="no ejecutado")
    args = ap.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    result = analyze(plan)
    md = render(result, args.fmt, args.validate, args.plan.name)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 2 if result["problems"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
