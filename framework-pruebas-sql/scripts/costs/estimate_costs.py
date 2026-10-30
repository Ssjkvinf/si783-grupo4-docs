#!/usr/bin/env python3
"""
Reporte de costos ESTIMADOS de un plan de Terraform.

Qué es: una estimación mensual (730 h) con los precios de LISTA que publica la API pública
«Azure Retail Prices» (https://prices.azure.com, sin cuenta ni credenciales), en USD.
Qué NO es: gasto real. No incluye impuestos, descuentos, créditos educativos, tráfico de salida,
transacciones, uso real de almacenamiento ni el costo de la VM que Terraform no gestiona.
Si no puede estimar un recurso lo dice («sin estimar») y no inventa una cifra.

Uso:
  python estimate_costs.py --plan tfplan.json --out-dir reportes/costos \
      [--existing-vm-size Standard_B2s --existing-vm-location eastus2] [--backup-gb 5] \
      [--real-costs costos_reales.json]

`tfplan.json` es la salida de `terraform show -json tfplan`.
El gasto REAL (si se pasa --real-costs) viene de otro paso del workflow (Cost Management) y se
presenta en una sección aparte: nunca se mezcla con la estimación.
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

HOURS_PER_MONTH = 730
PRICES_URL = "https://prices.azure.com/api/retail/prices"

# Recursos de Azure que no tienen cargo propio (se cobran por lo que contienen o son gratuitos).
NO_OWN_CHARGE = {
    "azurerm_resource_group", "azurerm_virtual_network", "azurerm_subnet",
    "azurerm_network_security_group", "azurerm_subnet_network_security_group_association",
    "azurerm_network_interface", "azurerm_storage_container", "azurerm_storage_management_policy",
    "azurerm_consumption_budget_resource_group", "terraform_data",
}

DISK_TIERS = {
    # tipo de almacenamiento -> (productName, prefijo, [(tamaño máx GB, nivel)])
    "Premium_LRS": ("Premium SSD Managed Disks", [(4, "P1"), (8, "P2"), (16, "P3"), (32, "P4"), (64, "P6"), (128, "P10"),
                                                   (256, "P15"), (512, "P20"), (1024, "P30"), (2048, "P40")]),
    "StandardSSD_LRS": ("Standard SSD Managed Disks", [(4, "E1"), (8, "E2"), (16, "E3"), (32, "E4"), (64, "E6"), (128, "E10"),
                                                        (256, "E15"), (512, "E20"), (1024, "E30"), (2048, "E40")]),
    "Standard_LRS": ("Standard HDD Managed Disks", [(32, "S4"), (64, "S6"), (128, "S10"), (256, "S15"), (512, "S20"),
                                                     (1024, "S30"), (2048, "S40")]),
}


# ------------------------------------------------------------------------- precios

def fetch_prices(flt: str, timeout: int = 30) -> List[Dict[str, Any]]:
    """Consulta la API pública de precios (solo lectura). Sigue la paginación."""
    url = PRICES_URL + "?currencyCode=USD&$filter=" + urllib.parse.quote(flt)
    items: List[Dict[str, Any]] = []
    while url:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310 (URL fija https)
            data = json.load(resp)
        items.extend(data.get("Items", []))
        url = data.get("NextPageLink")
    return items


def _first(items: List[Dict[str, Any]], predicate) -> Optional[Dict[str, Any]]:
    for it in items:
        if predicate(it):
            return it
    return None


def price_vm(size: str, location: str, fetch=fetch_prices) -> Tuple[Optional[float], str]:
    items = fetch(f"serviceName eq 'Virtual Machines' and armRegionName eq '{location}' and armSkuName eq '{size}' and priceType eq 'Consumption'")
    it = _first(items, lambda i: i.get("unitOfMeasure") == "1 Hour" and "Windows" not in i.get("productName", "")
                and "Spot" not in i.get("skuName", "") and "Low Priority" not in i.get("skuName", "") and i.get("retailPrice", 0) > 0)
    if not it:
        return None, f"sin precio Linux de lista para {size} en {location}"
    return it["retailPrice"] * HOURS_PER_MONTH, f"{it['retailPrice']} USD/h × {HOURS_PER_MONTH} h ({it['productName']}, {it['skuName']})"


def disk_tier(storage_type: str, size_gb: float) -> Optional[Tuple[str, str]]:
    if storage_type not in DISK_TIERS:
        return None
    product, tiers = DISK_TIERS[storage_type]
    for max_gb, tier in tiers:
        if size_gb <= max_gb:
            return product, tier
    return None


def price_disk(storage_type: str, size_gb: float, location: str, fetch=fetch_prices) -> Tuple[Optional[float], str]:
    t = disk_tier(storage_type, size_gb)
    if not t:
        return None, f"tipo de disco {storage_type} o tamaño {size_gb} GB sin tabla de niveles"
    product, tier = t
    items = fetch(f"serviceName eq 'Storage' and armRegionName eq '{location}' and productName eq '{product}' and meterName eq '{tier} LRS Disk'")
    it = _first(items, lambda i: i.get("unitOfMeasure") == "1/Month" and i.get("retailPrice", 0) > 0)
    if not it:
        return None, f"sin precio de lista para {product} {tier} en {location}"
    return it["retailPrice"], f"{it['retailPrice']} USD/mes (nivel {tier}, {product}; no incluye transacciones)"


def price_public_ip(sku: str, method: str, location: str, fetch=fetch_prices) -> Tuple[Optional[float], str]:
    items = fetch(f"serviceName eq 'Virtual Network' and armRegionName eq '{location}' and contains(productName, 'IP Addresses') and priceType eq 'Consumption'")
    kind = "Static" if method == "Static" else "Dynamic"
    it = _first(items, lambda i: i.get("skuName") == sku and f"{kind} Public IP" in i.get("meterName", "")
                and i.get("unitOfMeasure") == "1 Hour" and i.get("retailPrice", 0) > 0)
    if not it:
        return None, f"sin precio de lista para IP pública {sku}/{method} en {location}"
    return it["retailPrice"] * HOURS_PER_MONTH, f"{it['retailPrice']} USD/h × {HOURS_PER_MONTH} h ({it['meterName']})"


def price_storage(tier: str, location: str, gb: float, fetch=fetch_prices) -> Tuple[Optional[float], str]:
    items = fetch(f"serviceName eq 'Storage' and armRegionName eq '{location}' and productName eq 'General Block Blob v2' and skuName eq '{tier} LRS' and priceType eq 'Consumption'")
    it = _first(items, lambda i: i.get("meterName", "").endswith("Data Stored") and i.get("unitOfMeasure") == "1 GB/Month")
    if not it:
        return None, f"sin precio de lista para almacenamiento {tier} LRS en {location}"
    return it["retailPrice"] * gb, (f"{it['retailPrice']} USD/GB·mes × {gb} GB SUPUESTOS (el uso real depende de cuántas copias haya; "
                                    "no incluye operaciones ni transferencia)")


# ------------------------------------------------------------------------- plan

def load_plan(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def planned_resources(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Recursos gestionados del estado final planificado + su acción (create/update/no-op/…)."""
    actions: Dict[str, List[str]] = {rc["address"]: rc["change"]["actions"] for rc in plan.get("resource_changes", [])}
    out: List[Dict[str, Any]] = []

    def walk(module: Dict[str, Any]):
        for r in module.get("resources", []):
            if r.get("mode") == "managed":
                out.append({"address": r["address"], "type": r["type"], "values": r.get("values", {}),
                            "actions": actions.get(r["address"], ["no-op"])})
        for child in module.get("child_modules", []):
            walk(child)

    walk(plan.get("planned_values", {}).get("root_module", {}))
    return out


def action_label(actions: List[str]) -> str:
    if actions == ["no-op"]:
        return "sin cambios"
    if "delete" in actions and "create" in actions:
        return "REEMPLAZO"
    if "create" in actions:
        return "nuevo"
    if "update" in actions:
        return "cambio"
    if "delete" in actions:
        return "ELIMINACIÓN"
    return "/".join(actions)


def estimate_resource(res: Dict[str, Any], backup_gb: float, fetch=fetch_prices) -> Dict[str, Any]:
    t, v = res["type"], res["values"]
    line = {"address": res["address"], "type": t, "accion": action_label(res["actions"]),
            "estado": "estimado", "usd_mes": 0.0, "detalle": []}
    parts: List[Tuple[Optional[float], str]] = []
    try:
        if t == "azurerm_linux_virtual_machine":
            loc = v.get("location")
            parts.append(price_vm(v.get("size", ""), loc, fetch))
            od = (v.get("os_disk") or [{}])[0]
            parts.append(price_disk(od.get("storage_account_type", "StandardSSD_LRS"), float(od.get("disk_size_gb") or 30), loc, fetch))
        elif t == "azurerm_public_ip":
            parts.append(price_public_ip(v.get("sku", "Standard"), v.get("allocation_method", "Static"), v.get("location"), fetch))
        elif t == "azurerm_storage_account":
            parts.append(price_storage(v.get("access_tier", "Hot"), v.get("location"), backup_gb, fetch))
        elif t in NO_OWN_CHARGE:
            line["estado"] = "sin cargo propio"
            line["detalle"].append("no tiene tarifa propia (o se cobra por lo que contiene)")
            return line
        else:
            line["estado"] = "sin estimar"
            line["detalle"].append(f"no hay estimador para {t}")
            return line
    except Exception as exc:  # red caída, API cambiada, etc.: se informa, no se inventa
        line["estado"] = "sin estimar"
        line["detalle"].append(f"no se pudo consultar la API de precios: {exc}")
        return line

    total = 0.0
    missing = False
    for amount, text in parts:
        line["detalle"].append(text)
        if amount is None:
            missing = True
        else:
            total += amount
    line["usd_mes"] = round(total, 2)
    if missing:
        line["estado"] = "estimación parcial" if total > 0 else "sin estimar"
    return line


def render_markdown(report: Dict[str, Any]) -> str:
    m = []
    m.append("# Reporte de costos del plan de Terraform")
    m.append("")
    m.append(f"> **ESTIMACIÓN, no gasto real.** Precios de lista públicos de Azure Retail Prices, consultados el "
             f"{report['consultado_utc']} (USD, {HOURS_PER_MONTH} h/mes). No incluyen impuestos, descuentos, créditos educativos, "
             "tráfico de salida, transacciones ni el uso real. Un recurso «sin estimar» NO cuesta cero: simplemente no se pudo calcular.")
    m.append("")
    m.append("## 1. Estimación de los recursos que gestiona Terraform")
    m.append("")
    m.append("| Recurso | Acción en el plan | Estado de la estimación | USD/mes (estimado) | Cómo se calculó |")
    m.append("| --- | --- | --- | ---: | --- |")
    for r in report["recursos"]:
        monto = f"{r['usd_mes']:.2f}" if r["estado"] in ("estimado", "estimación parcial") else "—"
        m.append(f"| `{r['address']}` | {r['accion']} | {r['estado']} | {monto} | {'; '.join(r['detalle']) or '—'} |")
    m.append("")
    t = report["totales"]
    m.append(f"**Total estimado de estos recursos: {t['estado_final_usd_mes']:.2f} USD/mes** "
             f"(de los cuales {t['nuevos_o_cambiados_usd_mes']:.2f} USD/mes corresponden a recursos nuevos o con cambios en este plan).")
    if t["sin_estimar"]:
        m.append("")
        m.append(f"⚠ Hay {t['sin_estimar']} recurso(s) sin estimar o con estimación parcial: el total es un mínimo conocido, no un tope.")
    m.append("")
    m.append("## 2. VM existente (referencial)")
    m.append("")
    e = report["vm_existente"]
    if e:
        m.append(f"La VM existente **no la gestiona Terraform** y este plan no la modifica. Costo de lista de referencia para `{e['tamano']}` en `{e['region']}`: "
                 f"**{e['usd_mes']:.2f} USD/mes** encendida las 24 h ({e['detalle']}). No incluye su disco, IP ni tráfico. No se suma al total anterior."
                 if e["usd_mes"] is not None else
                 f"No se pudo estimar `{e['tamano']}` en `{e['region']}`: {e['detalle']}.")
    else:
        m.append("No se indicó el tamaño de la VM existente (variable `EXISTING_VM_SIZE`): su costo no figura en este reporte.")
    m.append("")
    m.append("## 3. Gasto real")
    m.append("")
    g = report["gasto_real"]
    if g:
        m.append("Datos de Azure Cost Management (periodo y moneda tal como los devolvió Azure; **son gasto real, no estimación**):")
        m.append("")
        m.append("```json")
        m.append(json.dumps(g, indent=2, ensure_ascii=False))
        m.append("```")
    else:
        m.append("**No disponible en esta ejecución.** El gasto real exige un permiso de lectura de costos (rol «Cost Management Reader» "
                 "o «Reader» sobre la suscripción/grupo de recursos) y activar el paso opcional del workflow (variable `COST_REAL_ENABLED=true`). "
                 "Mientras tanto, consulte «Cost Management + Billing» en el portal de Azure.")
    m.append("")
    m.append("## 4. Supuestos y límites")
    m.append("")
    for s in report["supuestos"]:
        m.append(f"- {s}")
    return "\n".join(m) + "\n"


def build_report(plan: Dict[str, Any], backup_gb: float, existing_size: str, existing_location: str,
                 real_costs: Optional[Any], fetch=None) -> Dict[str, Any]:
    # Se busca `fetch_prices` al llamar (no al definir la función) para poder sustituirla en las pruebas.
    fetch = fetch or (lambda flt: fetch_prices(flt))
    lines = [estimate_resource(r, backup_gb, fetch) for r in planned_resources(plan)]
    total = sum(r["usd_mes"] for r in lines)
    changed = sum(r["usd_mes"] for r in lines if r["accion"] in ("nuevo", "cambio", "REEMPLAZO"))
    unestimated = sum(1 for r in lines if r["estado"] in ("sin estimar", "estimación parcial"))

    existing = None
    if existing_size and existing_location:
        try:
            amount, detail = price_vm(existing_size, existing_location, fetch)
        except Exception as exc:
            amount, detail = None, f"no se pudo consultar la API de precios: {exc}"
        existing = {"tamano": existing_size, "region": existing_location, "usd_mes": None if amount is None else round(amount, 2), "detalle": detail}

    return {
        "tipo": "ESTIMACION_NO_GASTO_REAL",
        "consultado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "moneda": "USD",
        "horas_por_mes": HOURS_PER_MONTH,
        "recursos": lines,
        "totales": {"estado_final_usd_mes": round(total, 2), "nuevos_o_cambiados_usd_mes": round(changed, 2), "sin_estimar": unestimated},
        "vm_existente": existing,
        "gasto_real": real_costs,
        "supuestos": [
            f"Se asume {backup_gb} GB almacenados de copias (parámetro --backup-gb); el costo real depende de cuántas copias haya y de la política de retención.",
            "Redundancia LRS y nivel de acceso Cool para las copias (según la configuración de Terraform).",
            "Los precios son de lista (pay-as-you-go) en USD; su suscripción puede tener otros precios, créditos o descuentos.",
            "Los costos de tráfico saliente, transacciones de disco, soporte e impuestos no están incluidos.",
        ],
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plan", required=True, type=Path, help="JSON del plan (terraform show -json)")
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--backup-gb", type=float, default=5.0, help="GB de copias que se asumen almacenadas (supuesto)")
    ap.add_argument("--existing-vm-size", default="")
    ap.add_argument("--existing-vm-location", default="")
    ap.add_argument("--real-costs", type=Path, default=None, help="JSON con el gasto real (opcional)")
    args = ap.parse_args(argv)

    real = None
    if args.real_costs and args.real_costs.exists():
        real = json.loads(args.real_costs.read_text(encoding="utf-8"))
    report = build_report(load_plan(args.plan), args.backup_gb, args.existing_vm_size, args.existing_vm_location, real)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "cost_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md = render_markdown(report)
    (args.out_dir / "cost_report.md").write_text(md, encoding="utf-8")
    sys.stdout.write(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
