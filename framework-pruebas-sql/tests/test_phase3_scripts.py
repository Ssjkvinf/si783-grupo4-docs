"""
Pruebas de la Fase 3 que NO necesitan Azure, GitHub ni Docker:
  - scripts de reportes (plan de Terraform, costos, JUnit),
  - copia de seguridad consistente + restauración aislada de la SQLite,
  - comprobaciones estáticas de Terraform, Liquibase, workflows y scripts de despliegue.

Lo que sí requiere Azure/GitHub (ejecutar un plan real, desplegar, subir a Blob) NO se prueba aquí: ver docs/operacion-fase3.md.
"""
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]            # framework-pruebas-sql
REPO = ROOT.parent
for sub in ("backup", "costs", "reports", "db"):
    sys.path.insert(0, str(ROOT / "scripts" / sub))

import estimate_costs  # noqa: E402
import junit_to_md  # noqa: E402
import liquibase_report  # noqa: E402
import sqlite_backup  # noqa: E402
import sqlite_restore_verify  # noqa: E402
import terraform_plan_report  # noqa: E402


# ============================================================ planes sintéticos (mismo formato que `terraform show -json`)

def _plan(resources):
    return {
        "format_version": "1.2",
        "planned_values": {"root_module": {"resources": [
            {"address": r[0], "mode": "managed", "type": r[1], "values": r[2]} for r in resources]}},
        "resource_changes": [
            {"address": r[0], "mode": "managed", "type": r[1], "change": {"actions": r[3]}} for r in resources],
    }


PLAN_EXISTENTE = _plan([
    ("azurerm_storage_account.backups[0]", "azurerm_storage_account", {"location": "eastus2", "access_tier": "Cool"}, ["create"]),
    ("azurerm_storage_container.backups[0]", "azurerm_storage_container", {}, ["create"]),
])
PLAN_VM_NUEVA = _plan([
    ("azurerm_public_ip.new[0]", "azurerm_public_ip", {"location": "eastus2", "sku": "Standard", "allocation_method": "Static"}, ["create"]),
    ("azurerm_linux_virtual_machine.new[0]", "azurerm_linux_virtual_machine",
     {"location": "eastus2", "size": "Standard_B2s", "os_disk": [{"storage_account_type": "StandardSSD_LRS", "disk_size_gb": 64}]}, ["create"]),
])
PLAN_REEMPLAZA_VM = _plan([
    ("azurerm_linux_virtual_machine.adoptada[0]", "azurerm_linux_virtual_machine", {"location": "eastus2", "size": "Standard_B2s"}, ["delete", "create"]),
])
PLAN_SIN_CAMBIOS = _plan([
    ("azurerm_storage_account.backups[0]", "azurerm_storage_account", {"location": "eastus2"}, ["no-op"]),
])


def precios_falsos(flt, timeout=30):
    """Sustituye a la API pública de precios para que las pruebas no dependan de Internet."""
    if "Virtual Machines" in flt:
        return [{"productName": "Virtual Machines BS Series", "skuName": "B2s", "unitOfMeasure": "1 Hour", "retailPrice": 0.04}]
    if "Managed Disks" in flt:
        return [{"productName": "Standard SSD Managed Disks", "meterName": "E6 LRS Disk", "unitOfMeasure": "1/Month", "retailPrice": 5.0}]
    if "IP Addresses" in flt:
        return [{"productName": "IP Addresses", "skuName": "Standard", "meterName": "Standard IPv4 Static Public IP",
                 "unitOfMeasure": "1 Hour", "retailPrice": 0.005}]
    if "General Block Blob" in flt:
        return [{"productName": "General Block Blob v2", "skuName": "Cool LRS", "meterName": "Cool LRS Data Stored",
                 "unitOfMeasure": "1 GB/Month", "retailPrice": 0.01}]
    return []


# ======================================================================== reporte de costos

def test_costos_se_presentan_como_estimacion_y_no_como_gasto_real():
    rep = estimate_costs.build_report(PLAN_VM_NUEVA, 5.0, "", "", None, fetch=precios_falsos)
    md = estimate_costs.render_markdown(rep)

    assert rep["tipo"] == "ESTIMACION_NO_GASTO_REAL"
    assert "ESTIMACIÓN, no gasto real" in md
    assert "## 3. Gasto real" in md and "No disponible en esta ejecución" in md
    vm = next(r for r in rep["recursos"] if r["type"] == "azurerm_linux_virtual_machine")
    assert vm["usd_mes"] == pytest.approx(0.04 * 730 + 5.0)        # VM 24 h + disco E6
    ip = next(r for r in rep["recursos"] if r["type"] == "azurerm_public_ip")
    assert ip["usd_mes"] == pytest.approx(0.005 * 730)
    assert rep["totales"]["estado_final_usd_mes"] == pytest.approx(vm["usd_mes"] + ip["usd_mes"], abs=0.02)


def test_costos_si_la_api_falla_no_se_inventa_una_cifra():
    def api_caida(flt, timeout=30):
        raise OSError("sin red")

    rep = estimate_costs.build_report(PLAN_VM_NUEVA, 5.0, "Standard_B2s", "eastus2", None, fetch=api_caida)

    assert all(r["estado"] == "sin estimar" for r in rep["recursos"])
    assert rep["totales"]["estado_final_usd_mes"] == 0 and rep["totales"]["sin_estimar"] == 2
    assert rep["vm_existente"]["usd_mes"] is None
    md = estimate_costs.render_markdown(rep)
    assert "NO cuesta cero" in md and "sin estimar" in md


def test_costos_recurso_sin_precio_queda_sin_estimar():
    rep = estimate_costs.build_report(PLAN_EXISTENTE, 5.0, "", "", None, fetch=lambda f, timeout=30: [])
    cuenta = next(r for r in rep["recursos"] if r["type"] == "azurerm_storage_account")
    assert cuenta["estado"] == "sin estimar"
    contenedor = next(r for r in rep["recursos"] if r["type"] == "azurerm_storage_container")
    assert contenedor["estado"] == "sin cargo propio"


def test_costos_vm_existente_es_referencial_y_no_se_suma():
    rep = estimate_costs.build_report(PLAN_EXISTENTE, 5.0, "Standard_B2s", "eastus2", None, fetch=precios_falsos)
    assert rep["vm_existente"]["usd_mes"] == pytest.approx(0.04 * 730)
    assert rep["totales"]["estado_final_usd_mes"] < 1.0                 # solo la cuenta de almacenamiento
    assert "no la gestiona Terraform" in estimate_costs.render_markdown(rep)


def test_costos_el_gasto_real_va_en_su_propia_seccion():
    real = {"properties": {"rows": [[12.34, "USD"]]}}
    md = estimate_costs.render_markdown(estimate_costs.build_report(PLAN_EXISTENTE, 5.0, "", "", real, fetch=precios_falsos))
    assert "son gasto real, no estimación" in md and "12.34" in md


def test_costos_niveles_de_disco():
    assert estimate_costs.disk_tier("StandardSSD_LRS", 64) == ("Standard SSD Managed Disks", "E6")
    assert estimate_costs.disk_tier("Premium_LRS", 100) == ("Premium SSD Managed Disks", "P10")
    assert estimate_costs.disk_tier("Desconocido", 64) is None


def test_costos_script_de_linea_de_comandos_genera_los_archivos(tmp_path, monkeypatch):
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps(PLAN_EXISTENTE), encoding="utf-8")
    monkeypatch.setattr(estimate_costs, "fetch_prices", precios_falsos)     # sin Internet

    rc = estimate_costs.main(["--plan", str(plan), "--out-dir", str(tmp_path / "out"), "--existing-vm-size", "Standard_B2s",
                              "--existing-vm-location", "eastus2"])

    assert rc == 0
    datos = json.loads((tmp_path / "out" / "cost_report.json").read_text(encoding="utf-8"))
    assert datos["tipo"] == "ESTIMACION_NO_GASTO_REAL" and datos["moneda"] == "USD"
    assert "ESTIMACIÓN, no gasto real" in (tmp_path / "out" / "cost_report.md").read_text(encoding="utf-8")


# ================================================================ reporte del plan

def test_plan_sin_cambios_se_indica_claramente(tmp_path):
    plan = tmp_path / "p.json"
    plan.write_text(json.dumps(PLAN_SIN_CAMBIOS))
    rc = terraform_plan_report.main(["--plan", str(plan), "--out", str(tmp_path / "r.md")])
    assert rc == 0
    assert "No hay cambios de infraestructura" in (tmp_path / "r.md").read_text(encoding="utf-8")


def test_plan_que_reemplaza_la_vm_se_bloquea(tmp_path):
    plan = tmp_path / "p.json"
    plan.write_text(json.dumps(PLAN_REEMPLAZA_VM))
    rc = terraform_plan_report.main(["--plan", str(plan), "--out", str(tmp_path / "r.md")])
    md = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert rc == 2
    assert "BLOQUEADO" in md and "REEMPLAZO" in md


def test_plan_con_eliminacion_o_cambio_de_vm_existente_se_bloquea():
    eliminar = _plan([("azurerm_storage_account.x", "azurerm_storage_account", {}, ["delete"])])
    assert terraform_plan_report.analyze(eliminar)["problems"]
    modificar_vm = _plan([("azurerm_linux_virtual_machine.x", "azurerm_linux_virtual_machine", {}, ["update"])])
    assert terraform_plan_report.analyze(modificar_vm)["problems"]


def test_plan_solo_con_creaciones_es_apto(tmp_path):
    plan = tmp_path / "p.json"
    plan.write_text(json.dumps(PLAN_EXISTENTE))
    assert terraform_plan_report.main(["--plan", str(plan), "--out", str(tmp_path / "r.md")]) == 0


# ======================================================================== reporte JUnit

def _junit(tmp_path, tests, failures, errors, skipped, casos):
    xml = f'<testsuites><testsuite tests="{tests}" failures="{failures}" errors="{errors}" skipped="{skipped}" time="1.5">{casos}</testsuite></testsuites>'
    p = tmp_path / "j.xml"
    p.write_text(xml)
    return p


def test_junit_las_omitidas_no_cuentan_como_aprobadas(tmp_path):
    casos = '<testcase classname="a" name="ok"/><testcase classname="a" name="omitida"><skipped/></testcase>'
    j = _junit(tmp_path, 2, 0, 0, 1, casos)
    r = junit_to_md.summarize(j)
    assert (r["total"], r["passed"], r["skipped"]) == (2, 1, 1)
    assert junit_to_md.main(["--junit", str(j), "--out", str(tmp_path / "o.md")]) == 0
    assert "omitidas no se cuentan como aprobadas" in (tmp_path / "o.md").read_text(encoding="utf-8")


def test_junit_con_fallos_devuelve_error(tmp_path):
    casos = '<testcase classname="a" name="mala"><failure message="x"/></testcase>'
    j = _junit(tmp_path, 1, 1, 0, 0, casos)
    assert junit_to_md.main(["--junit", str(j), "--out", str(tmp_path / "o.md")]) == 1
    assert "a::mala" in (tmp_path / "o.md").read_text(encoding="utf-8")


# ================================================================ copia de seguridad y restauración

def _crear_base_con_datos(path: Path):
    """Base real: esquema de Alembic + datos de ejemplo (sin contraseñas, como la aplicación)."""
    import os
    env = dict(os.environ, FRAMEWORK_DB_URL=f"sqlite:///{path.as_posix()}")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)
    conn = sqlite3.connect(path)
    conn.execute("INSERT INTO projects (name, description) VALUES ('Proyecto de prueba', 'demo')")
    pid = conn.execute("SELECT id FROM projects WHERE name = 'Proyecto de prueba'").fetchone()[0]
    conn.execute("INSERT INTO connection_profiles (project_id, name, engine, host, port, service_name, username, environment_type) "
                 "VALUES (?, 'perfil', 'ORACLE', 'oracle.local', 1521, 'FREEPDB1', 'u', 'TEST')", (pid,))
    conn.execute("INSERT INTO test_cases (project_id, name, sql_query, expected_result, validation_type) "
                 "VALUES (?, 'caso', 'SELECT 1 FROM DUAL', '1', 'ROW_COUNT')", (pid,))
    conn.execute("INSERT INTO test_suites (project_id, name) VALUES (?, 'suite')", (pid,))
    conn.execute("INSERT INTO execution_history (project_id, status, duration_ms, executed_sql) VALUES (?, 'PASS', 1.5, 'SELECT 1 FROM DUAL')", (pid,))
    conn.commit()
    conn.close()


@pytest.fixture()
def base_activa(tmp_path):
    ruta = tmp_path / "activa" / "framework_interno.sqlite"
    ruta.parent.mkdir()
    _crear_base_con_datos(ruta)
    return ruta


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_copia_consistente_genera_manifiesto_con_hash_tamano_e_integridad(base_activa, tmp_path):
    antes = _sha(base_activa)
    destino = tmp_path / "copias"

    manifest = sqlite_backup.make_backup(base_activa, destino, "framework_interno", compress=True)

    assert manifest["ok"] is True
    assert manifest["integrity_check"] == ["ok"] and manifest["foreign_key_violations"] == 0
    # projects = 2: «Proyecto general» (lo crea la migración 001) + el de la prueba
    assert manifest["filas_por_tabla"]["projects"] == 2 and manifest["filas_por_tabla"]["execution_history"] == 1
    archivo = destino / manifest["archivo"]
    assert archivo.name.endswith(".sqlite.gz") and archivo.stat().st_size == manifest["tamano_bytes"] > 0
    assert _sha(archivo) == manifest["sha256"]
    assert manifest["alembic_version"] == "a4b8c2d9e1f0"
    assert _sha(base_activa) == antes, "la copia no debe modificar la base de origen"


def test_copia_no_se_hace_si_el_destino_es_la_carpeta_de_la_base_activa(base_activa):
    with pytest.raises(ValueError):
        sqlite_backup.make_backup(base_activa, base_activa.parent, "x", compress=False)


def test_copia_no_sobrescribe_otra_copia_ni_acepta_origen_inexistente(base_activa, tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        sqlite_backup.make_backup(tmp_path / "no_existe.sqlite", tmp_path / "c", "x", compress=False)
    destino = tmp_path / "c"
    sqlite_backup.make_backup(base_activa, destino, "mismo", compress=False)
    # mismo segundo, mismo prefijo -> debe negarse en lugar de pisar la copia
    monkeypatch.setattr(sqlite_backup, "datetime", type("D", (), {"now": staticmethod(lambda tz=None: __import__("datetime").datetime(2026, 1, 1, tzinfo=__import__("datetime").timezone.utc))}))
    sqlite_backup.make_backup(base_activa, destino, "fijo", compress=False)
    with pytest.raises(FileExistsError):
        sqlite_backup.make_backup(base_activa, destino, "fijo", compress=False)


def test_copia_es_consistente_aunque_haya_escrituras_en_curso(base_activa, tmp_path):
    """
    Un escritor inserta PARES de filas en una sola transacción mientras se hacen copias.
    En una instantánea coherente la cantidad de filas es siempre PAR y la integridad es correcta.
    """
    conn = sqlite3.connect(base_activa)
    conn.execute("CREATE TABLE pares (id INTEGER PRIMARY KEY AUTOINCREMENT, lote INTEGER)")
    conn.commit()
    conn.close()
    parar = threading.Event()
    errores = []

    def escritor():
        c = sqlite3.connect(base_activa, timeout=30, isolation_level=None)
        n = 0
        try:
            while not parar.is_set():
                n += 1
                c.execute("BEGIN IMMEDIATE")
                c.execute("INSERT INTO pares (lote) VALUES (?)", (n,))
                c.execute("INSERT INTO pares (lote) VALUES (?)", (n,))
                c.execute("COMMIT")
        except Exception as exc:   # pragma: no cover
            errores.append(exc)
        finally:
            c.close()

    hilo = threading.Thread(target=escritor)
    hilo.start()
    try:
        time.sleep(0.2)
        for i in range(15):
            m = sqlite_backup.make_backup(base_activa, tmp_path / f"c{i}", "framework_interno", compress=False)
            assert m["ok"], m
            assert m["filas_por_tabla"]["pares"] % 2 == 0, "la copia mezcla transacciones: no es una instantánea coherente"
    finally:
        parar.set()
        hilo.join()
    assert not errores


def test_restauracion_aislada_lee_los_datos_y_no_toca_la_base_activa(base_activa, tmp_path):
    antes = _sha(base_activa)
    m = sqlite_backup.make_backup(base_activa, tmp_path / "copias", "framework_interno", compress=True)
    work = tmp_path / "restauracion"

    res = sqlite_restore_verify.restore(tmp_path / "copias" / m["archivo"], m, work, active_db=base_activa)

    assert res["ok"], res["checks"]
    assert (work / "restaurada.sqlite").exists()
    assert res["muestras"]["projects"] == 2
    assert res["muestras"]["proyectos_ejemplo"] == ["Proyecto general", "Proyecto de prueba"]
    assert res["muestras"]["execution_history"] == 1
    assert _sha(base_activa) == antes, "restaurar no debe tocar la base activa"
    # la base restaurada se puede abrir y consultar con normalidad
    c = sqlite3.connect(work / "restaurada.sqlite")
    assert c.execute("SELECT name FROM test_cases").fetchone()[0] == "caso"
    c.close()


def test_restauracion_detecta_una_copia_alterada(base_activa, tmp_path):
    m = sqlite_backup.make_backup(base_activa, tmp_path / "copias", "framework_interno", compress=True)
    archivo = tmp_path / "copias" / m["archivo"]
    datos = bytearray(archivo.read_bytes())
    datos[len(datos) // 2] ^= 0xFF                       # corrompe un byte
    archivo.write_bytes(bytes(datos))

    res = sqlite_restore_verify.restore(archivo, m, tmp_path / "rest", active_db=None)

    assert res["ok"] is False
    assert res["restaurada"] is None                      # no se restauró nada
    assert not (tmp_path / "rest" / "restaurada.sqlite").exists()


def test_restauracion_rechaza_carpeta_ocupada_y_destino_igual_a_la_base_activa(base_activa, tmp_path):
    m = sqlite_backup.make_backup(base_activa, tmp_path / "copias", "framework_interno", compress=False)
    archivo = tmp_path / "copias" / m["archivo"]

    ocupada = tmp_path / "ocupada"
    ocupada.mkdir()
    (ocupada / "algo.txt").write_text("x")
    with pytest.raises(sqlite_restore_verify.RestoreError):
        sqlite_restore_verify.restore(archivo, m, ocupada, None)

    work = tmp_path / "w"
    with pytest.raises(sqlite_restore_verify.RestoreError):
        sqlite_restore_verify.restore(archivo, m, work, active_db=work / "restaurada.sqlite")


def test_reportes_de_copia_y_restauracion_no_contienen_datos(base_activa, tmp_path):
    destino = tmp_path / "copias"
    assert sqlite_backup.main(["--db", str(base_activa), "--out-dir", str(destino), "--gzip"]) == 0
    reportes = list(destino.glob("*.reporte.md"))
    manifiestos = list(destino.glob("*.manifest.json"))
    assert len(reportes) == len(manifiestos) == 1
    texto = reportes[0].read_text(encoding="utf-8") + manifiestos[0].read_text(encoding="utf-8")
    for dato in ("Proyecto de prueba", "oracle.local", "SELECT 1 FROM DUAL"):
        assert dato not in texto, f"el reporte no debe contener datos de las tablas ({dato})"
    for campo in ("SHA-256", "integrity_check", "Tamaño", "Fecha"):
        assert campo in reportes[0].read_text(encoding="utf-8") or campo in manifiestos[0].read_text(encoding="utf-8")

    manifiesto = manifiestos[0]
    copia = destino / json.loads(manifiesto.read_text())["archivo"]
    rc = sqlite_restore_verify.main(["--backup", str(copia), "--manifest", str(manifiesto), "--work-dir", str(tmp_path / "r"),
                                     "--active-db", str(base_activa), "--report", str(tmp_path / "rest.md")])
    assert rc == 0
    assert "RESTAURACIÓN VERIFICADA" in (tmp_path / "rest.md").read_text(encoding="utf-8")


# ===================================================================== Terraform (estático)

TF_DIR = ROOT / "infra" / "terraform"


def _tf_text():
    return {p.name: p.read_text(encoding="utf-8") for p in TF_DIR.glob("*.tf")}


def test_terraform_por_defecto_usa_la_vm_existente_y_no_crea_ninguna_nueva():
    tf = _tf_text()
    assert re.search(r'variable "use_existing_vm"[^}]*default\s*=\s*true', tf["variables.tf"], re.S)
    assert re.search(r'variable "create_new_vm"[^}]*default\s*=\s*false', tf["variables.tf"], re.S)
    assert "CREATE-NEW-VM" in tf["variables.tf"]
    # todo recurso de la VM nueva existe solo bajo `count`
    recursos = re.findall(r'resource "(azurerm_[a-z_]+)" "new" \{(.*?)\n\}\n', tf["vm_new.tf"], re.S)
    assert len(recursos) >= 7
    for tipo, cuerpo in recursos:
        assert "count" in cuerpo and "local.new_vm_enabled" in cuerpo, f"{tipo} no está protegido por count"
    # la VM existente se lee con data sources (no se gestiona)
    assert 'data "azurerm_virtual_machine" "existing"' in tf["main.tf"]
    assert not re.search(r'resource "azurerm_(linux|windows)_virtual_machine" "(existing|adopted)', "".join(tf.values()))
    assert "prevent_destroy = true" in tf["vm_new.tf"]


def test_terraform_no_contiene_secretos_ni_identificadores_reales():
    todo = "\n".join(p.read_text(encoding="utf-8") for p in TF_DIR.iterdir() if p.is_file() and p.suffix in {".tf", ".yaml", ".hcl"})
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", todo, re.I), "hay un GUID (¿suscripción/tenant?)"
    assert not re.search(r'(client_secret|access_key|sas_token|password|private_key)\s*=\s*"[^"$]', todo, re.I)
    assert "BEGIN" not in todo and "ssh-rsa AAAA" not in todo
    assert 'backend "azurerm" {}' in todo            # backend parcial: la configuración llega por -backend-config
    assert "ARM_CLIENT_SECRET" in todo               # documenta de dónde sale la credencial, sin valor


def test_terraform_formato_correcto_si_hay_binario():
    terraform = shutil.which("terraform")
    if not terraform:
        pytest.skip("terraform no está instalado en este entorno")
    r = subprocess.run([terraform, "fmt", "-check", "-recursive", str(TF_DIR)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


# ======================================================================== Liquibase (estático)

LB_DIR = ROOT / "infra" / "oracle" / "liquibase"


def test_liquibase_changelog_raiz_incluye_archivos_que_existen_y_ids_unicos():
    raiz = (LB_DIR / "changelog" / "db.changelog-root.yaml").read_text(encoding="utf-8")
    incluidos = re.findall(r"file:\s*(\S+\.sql)", raiz)
    assert len(incluidos) == 4
    ids = []
    for nombre in incluidos:
        sql = (LB_DIR / "changelog" / nombre).read_text(encoding="utf-8")
        assert sql.startswith("--liquibase formatted sql"), nombre
        sets = re.findall(r"^--changeset\s+(\S+)", sql, re.M)
        assert sets, nombre
        ids += sets
        assert re.search(r"context:", sql), f"{nombre}: falta context"
    assert len(ids) == len(set(ids)), "changesets duplicados"


def test_liquibase_los_objetos_se_crean_con_precondicion_para_adoptar_los_existentes():
    t = (LB_DIR / "changelog" / "001_tabla_framework_test_items.sql").read_text(encoding="utf-8")
    assert "MARK_RAN" in t and "user_tables" in t
    assert "DROP TABLE" not in t.replace("-- Sin rollback", "")       # no hay rollback que borre una tabla preexistente
    i = (LB_DIR / "changelog" / "002_indice_active.sql").read_text(encoding="utf-8")
    assert "MARK_RAN" in i and "user_indexes" in i and "--rollback DROP INDEX" in i


def test_liquibase_datos_de_demostracion_coinciden_con_el_script_de_carga():
    def filas(texto):
        return sorted(re.findall(r"VALUES\s*\(\s*(\d+)\s*,\s*'([^']*)'\s*,\s*(\d+)\s*\)", texto, re.I))

    lb = filas((LB_DIR / "changelog" / "004_datos_demostracion.sql").read_text(encoding="utf-8"))
    seed = filas((ROOT / "infra" / "oracle" / "demo" / "seed_demo_data.sql").read_text(encoding="utf-8"))
    assert lb == seed and len(lb) == 5
    assert "context:demo" in (LB_DIR / "changelog" / "004_datos_demostracion.sql").read_text(encoding="utf-8")


def test_liquibase_no_guarda_credenciales():
    for p in LB_DIR.rglob("*"):
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            assert not re.search(r"(password|passwd)\s*[:=]\s*\S+", t, re.I) or "COMMAND_PASSWORD" in t, p
    props = (LB_DIR / "liquibase.properties").read_text(encoding="utf-8")
    assert "url:" not in props and "username:" not in props and "password:" not in props


def test_liquibase_reporte_detecta_idempotencia_y_su_ausencia(tmp_path):
    def logs(run2_ejecutados):
        d = tmp_path / f"l{run2_ejecutados}"
        d.mkdir()
        (d / "00_validate.log").write_text("No validation errors found.\nLiquibase command 'validate' was executed successfully.")
        (d / "01_update_1.log").write_text("Liquibase Version: 4.33.0\nUPDATE SUMMARY\nRun:                          4\nPreviously run:               0\n"
                                           "Filtered out:                 0\nTotal change sets:            4\nLiquibase command 'update' was executed successfully.")
        (d / "02_update_2.log").write_text(f"UPDATE SUMMARY\nRun:                          {run2_ejecutados}\nPreviously run:               4\n"
                                           f"Filtered out:                 0\nTotal change sets:            4\nLiquibase command 'update' was executed successfully.")
        return d

    md, ok = liquibase_report.render(logs(0), "prueba", None)
    assert ok and "CORRECTA" in md
    md2, ok2 = liquibase_report.render(logs(2), "prueba", None)
    assert not ok2 and "FALLA" in md2


def test_liquibase_reporte_reconoce_los_changesets_marcados_como_ejecutados(tmp_path):
    """Líneas copiadas de una ejecución real de Liquibase 4.33 (adopción: la tabla ya existía)."""
    d = tmp_path / "adopcion"
    d.mkdir()
    (d / "01_update_1.log").write_text(
        'Marking ChangeSet: "changelog/001_tabla_framework_test_items.sql::001-tabla-framework-test-items::equipo" as ran despite '
        "precondition failure due to onFail='MARK_RAN':\n"
        "UPDATE SUMMARY\nRun:                          3\nPreviously run:               0\nFiltered out:                 0\n"
        "Total change sets:            4\nLiquibase command 'update' was executed successfully.\n")
    (d / "02_update_2.log").write_text("Run:                          0\nPreviously run:               3\nFiltered out:                 1\n"
                                       "Total change sets:            4\nLiquibase command 'update' was executed successfully.\n")
    md, ok = liquibase_report.render(d, "adopción", None)
    assert ok
    assert "001-tabla-framework-test-items" in md and "marcados como ejecutados sin aplicarse" in md


# ===================================================================== workflows (estático)

WF_DIR = REPO / ".github" / "workflows"


def _wf(nombre):
    return (WF_DIR / nombre).read_text(encoding="utf-8")


def _triggers(texto):
    bloque = re.search(r"^on:\n(.*?)^\S", texto + "\nx", re.S | re.M)
    return bloque.group(1) if bloque else ""


@pytest.mark.parametrize("nombre", ["deploy.yml", "release.yml"])
def test_despliegue_y_release_nunca_se_disparan_con_un_push(nombre):
    t = _triggers(_wf(nombre))
    assert "workflow_dispatch" in t or "workflow_call" in t
    for prohibido in ("push:", "pull_request", "schedule:"):
        assert prohibido not in t, f"{nombre} no debe dispararse con {prohibido}"


def test_infra_apply_exige_aprobacion_confirmacion_y_nunca_hay_destroy():
    t = _wf("infra.yml")
    assert "terraform destroy" not in t and "-auto-approve" not in t
    apply_job = t[t.index("  apply:"):]
    assert "environment: azure-apply" in apply_job
    assert "inputs.confirm_apply == 'APPLY'" in apply_job
    assert "terraform apply -input=false tfplan" in apply_job          # aplica el plan ya revisado
    # push y PR solo validan: el plan y el apply solo corren con workflow_dispatch
    assert "github.event_name == 'workflow_dispatch'" in t[t.index("  plan:"):t.index("  apply:")]
    trig = _triggers(t)
    assert "workflow_dispatch" in trig and "push:" in trig and "pull_request:" in trig


def test_infra_sin_secretos_no_fabrica_un_plan_verde():
    t = _wf("infra.yml")
    assert "Plan NO generado" in t and "Faltan secretos" in t and "exit 1" in t


def test_backup_programado_solo_actua_si_se_habilita_y_no_publica_la_copia_como_artefacto():
    t = _wf("backup.yml")
    assert "BACKUP_SCHEDULE_ENABLED == 'true'" in t
    artefactos = re.findall(r"upload-artifact@v4\s+if:[^\n]*\n\s+with:\s+name:[^\n]*\n\s+path:\s*([^\n]+)", t)
    assert artefactos and all(".sqlite" not in a and "trabajo" not in a for a in artefactos), artefactos
    assert "--auth-mode login" in t and "--no-overwrite" in t


def test_workflows_sin_secretos_incrustados_y_credenciales_solo_por_contexto_secrets():
    patrones = [r"ghp_[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}", r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY", r"sig=[A-Za-z0-9%]{20,}"]
    for p in WF_DIR.glob("*.yml"):
        t = p.read_text(encoding="utf-8")
        for pat in patrones:
            assert not re.search(pat, t), f"{p.name}: posible secreto incrustado ({pat})"
    assert "secrets." not in _wf("db-objects.yml"), "db-objects.yml no necesita secretos: todo es efímero"


def test_workflows_usan_entornos_para_lo_que_toca_azure_o_la_vm():
    assert "environment: azure-production" in _wf("deploy.yml")
    assert "environment: azure-backup" in _wf("backup.yml")
    assert "environment: azure-plan" in _wf("infra.yml")


def test_workflows_yaml_valido_si_hay_pyyaml():
    yaml = pytest.importorskip("yaml")
    for p in WF_DIR.glob("*.yml"):
        doc = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "jobs" in doc, p.name


# ======================================================================= scripts de despliegue (estático)

def _bash():
    """Un bash que funcione de verdad (en Windows `bash.exe` suele ser el lanzador de WSL, que puede no tener distribución)."""
    candidatos = [Path("C:/Program Files/Git/bin/bash.exe"), Path("C:/Program Files/Git/usr/bin/bash.exe"), shutil.which("bash")]
    for c in candidatos:
        if c and Path(c).exists():
            try:
                r = subprocess.run([str(c), "-c", "echo ok"], capture_output=True, text=True, timeout=20)
            except (OSError, subprocess.SubprocessError):
                continue
            if r.returncode == 0 and r.stdout.strip() == "ok":
                return str(c)
    return None


@pytest.mark.parametrize("ruta", ["scripts/deploy/deploy_remote.sh", "scripts/deploy/rollback_remote.sh",
                                  "scripts/backup/backup_vm.sh", "scripts/db/liquibase_demo.sh"])
def test_scripts_bash_tienen_sintaxis_valida_y_finales_lf(ruta):
    p = ROOT / ruta
    assert b"\r\n" not in p.read_bytes(), f"{ruta} debe tener finales de línea LF"
    bash = _bash()
    if not bash:
        pytest.skip("no hay un bash utilizable en este entorno")
    r = subprocess.run([bash, "-n", str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_scripts_de_despliegue_son_seguros_por_construccion():
    d = (ROOT / "scripts/deploy/deploy_remote.sh").read_text(encoding="utf-8")
    r = (ROOT / "scripts/deploy/rollback_remote.sh").read_text(encoding="utf-8")
    b = (ROOT / "scripts/backup/backup_vm.sh").read_text(encoding="utf-8")
    for texto in (d, r, b):
        assert "set -euo pipefail" in texto
        for peligro in ("docker compose down", "volume rm", "volume prune", "system prune", "docker rm", "--force-recreate", "rm -rf /"):
            assert peligro not in texto, f"comando peligroso: {peligro}"
    assert "up -d --no-build --no-deps api" in d              # solo se recrea el servicio api
    assert "Reversión automática" in d.replace("REVERSIÓN", "Reversión") and "wait_healthy" in d
    assert "SKIP_BACKUP" in d and "backup_vm.sh" in d         # copia previa obligatoria salvo opt-out explícito
    assert ":/data:ro" in b and "sqlite_backup.py" in b       # la copia abre el volumen en solo lectura
    # los secretos nunca viajan como argumentos de línea de comandos
    assert "--password-stdin" in d and "--password-stdin" in r


def test_compose_release_solo_cambia_la_imagen_de_la_api():
    yaml = pytest.importorskip("yaml")
    doc = yaml.safe_load((ROOT / "scripts/deploy/compose.release.yml").read_text(encoding="utf-8"))
    assert list(doc["services"]) == ["api"]
    api = doc["services"]["api"]
    assert set(api) == {"image", "pull_policy"}                 # no toca puertos, volúmenes, variables ni Oracle/Caddy
    assert "${API_IMAGE" in api["image"] and api["pull_policy"] == "never"
