"""
Fase 9A (preparación de Azure, sin tocar Azure): barrera del plan de Terraform, prueba de Terraform con proveedor simulado en CI y
valores de producción recomendados. Todo es estático o con planes JSON inventados; no usa credenciales.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "reports"))
import terraform_plan_report  # noqa: E402


def _plan(cambios):
    return {"resource_changes": [{"address": a, "type": t, "change": {"actions": acc}} for a, t, acc in cambios]}


@pytest.mark.parametrize("direccion,tipo,acciones", [
    ("azurerm_network_interface.vm", "azurerm_network_interface", ["update"]),
    ("azurerm_managed_disk.os", "azurerm_managed_disk", ["update"]),
    ("azurerm_public_ip.vm", "azurerm_public_ip", ["update"]),
    ("azurerm_network_security_group.vm", "azurerm_network_security_group", ["update"]),
    ("azurerm_resource_group.rg", "azurerm_resource_group", ["update"]),
    ("azurerm_virtual_machine_extension.x", "azurerm_virtual_machine_extension", ["update"]),
    ("azurerm_linux_virtual_machine.vm", "azurerm_linux_virtual_machine", ["update"]),
    ("azurerm_resource_group.rg", "azurerm_resource_group", ["delete"]),
    ("azurerm_storage_account.backups[0]", "azurerm_storage_account", ["delete", "create"]),
])
def test_la_barrera_bloquea_cambios_a_la_vm_o_a_lo_que_la_acompana(direccion, tipo, acciones):
    assert terraform_plan_report.analyze(_plan([(direccion, tipo, acciones)]))["problems"]


def test_la_barrera_bloquea_acciones_desconocidas():
    r = terraform_plan_report.analyze(_plan([("azurerm_storage_account.backups[0]", "azurerm_storage_account", ["forget"])]))
    assert r["problems"] and "acción no reconocida" in r["problems"][0]


@pytest.mark.parametrize("cambios", [
    [("azurerm_storage_account.backups[0]", "azurerm_storage_account", ["create"]),
     ("azurerm_storage_container.backups[0]", "azurerm_storage_container", ["create"]),
     ("azurerm_storage_management_policy.backups[0]", "azurerm_storage_management_policy", ["create"]),
     ("data.azurerm_virtual_machine.existing[0]", "azurerm_virtual_machine", ["read"])],
    [("azurerm_storage_management_policy.backups[0]", "azurerm_storage_management_policy", ["update"])],   # p. ej. cambiar la retención
    [("azurerm_linux_virtual_machine.new[0]", "azurerm_linux_virtual_machine", ["create"]),                # modo VM nueva confirmado
     ("azurerm_network_interface.new[0]", "azurerm_network_interface", ["create"])],
])
def test_la_barrera_deja_pasar_creaciones_lecturas_y_cambios_de_los_recursos_de_apoyo(cambios):
    assert terraform_plan_report.analyze(_plan(cambios))["problems"] == []


def test_ci_corre_terraform_test_con_proveedor_simulado_y_sin_secretos():
    t = (REPO / ".github" / "workflows" / "infra.yml").read_text(encoding="utf-8")
    validate = t[t.index("  validate:"):t.index("  tests:")]
    assert "terraform test" in validate and "secrets." not in validate
    prueba = (ROOT / "infra" / "terraform" / "tests" / "plan_por_defecto.tftest.hcl").read_text(encoding="utf-8")
    assert 'mock_provider "azurerm"' in prueba and "command = plan" in prueba
    assert "PRIVATE KEY" not in prueba
    # Los únicos identificadores con forma de GUID son ceros (ficticios).
    guids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", prueba, re.I)
    assert guids and set(guids) == {"00000000-0000-0000-0000-000000000000"}
    for run in ("por_defecto_lee_la_vm_y_solo_crea_el_almacenamiento_de_copias", "no_se_mezcla_la_vm_existente_con_una_nueva",
                "una_vm_nueva_exige_la_confirmacion_explicita"):
        assert f'run "{run}"' in prueba


def test_terraform_test_si_hay_binario_y_proveedor_ya_descargado():
    terraform = shutil.which("terraform")
    tf_dir = ROOT / "infra" / "terraform"
    if not terraform or not (tf_dir / ".terraform" / "providers").exists():
        pytest.skip("requiere terraform y `terraform init -backend=false` previo (descarga el proveedor; en CI lo hace infra.yml)")
    r = subprocess.run([terraform, "test", "-no-color"], cwd=tf_dir, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]


def test_produccion_cierra_el_registro_por_defecto():
    yaml = pytest.importorskip("yaml")
    api = yaml.safe_load((ROOT / "infra" / "production" / "compose.yml").read_text(encoding="utf-8"))["services"]["api"]
    assert "APP_REGISTRATION_ENABLED=${APP_REGISTRATION_ENABLED:-false}" in api["environment"]
    ejemplo = (ROOT / "infra" / "production" / ".env.production.example").read_text(encoding="utf-8")
    assert "APP_REGISTRATION_ENABLED=false" in ejemplo


def test_runbook_tiene_los_pasos_en_orden_sin_secretos_ni_identificadores_reales():
    t = (ROOT / "docs" / "runbook-azure.md").read_text(encoding="utf-8")
    posiciones = [t.index(f"\n## {letra}. ") for letra in "ABCDEFGHI"]
    assert posiciones == sorted(posiciones), "los pasos A-I deben ir en orden"
    for frase in ("DETÉNGASE", "estimación", "Create a merge commit", "Source: GitHub Actions", "azure-plan", "azure-backup",
                  "azure-apply", "azure-production", "--role Reader", "Storage Account Contributor", "preflight_vm.sh",
                  "Creaciones: 3", "revertir la imagen NO revierte los datos", "v1.0.0", "v1.0.1"):
        assert frase in t, frase
    assert "--role Contributor" not in t and "--role Owner" not in t
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", t, re.I)
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", t), "no debe haber IP reales"
    assert "BEGIN" not in t and "ghp_" not in t
