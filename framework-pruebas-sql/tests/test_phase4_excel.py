"""
Fase 4 — integración con Excel: plantilla, importación con validaciones, exportación de casos y de resultados.
Los archivos .xlsx se construyen y se vuelven a leer de verdad con openpyxl (no se simulan).
"""
import io
import zipfile

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook

from app.core.database import get_db
from app.main import app
from app.models.history import ExecutionHistory
from app.services import excel_io

client = TestClient(app)
HEADERS = ["Nombre", "Descripción", "SQL", "Validación", "Esperado", "Suites"]
OK_ROWS = [
    ["Hay 5 productos", "conteo", "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", 5, "Reglas"],
    ["Sin nombres vacíos", "", "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS WHERE TRIM(NAME) IS NULL", "valor", 0, "Reglas; Extra"],
    ["Existe el ID 3", None, "SELECT ID FROM FRAMEWORK_TEST_ITEMS WHERE ID = 3", "EXISTS", True, None],
    ["Filas devueltas", None, "SELECT ID FROM FRAMEWORK_TEST_ITEMS", "cantidad de filas", 5, None],
]


def xlsx(rows, headers=HEADERS, sheet="Casos"):
    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    ws.append(headers)
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def proyecto(nombre="P Excel"):
    return client.post("/api/projects/", json={"name": nombre}).json()["id"]


def importar(pid, contenido, **params):
    q = "&".join(f"{k}={str(v).lower() if isinstance(v, bool) else v}" for k, v in params.items())
    return client.post(f"/api/excel/cases/import?project_id={pid}&{q}", content=contenido,
                       headers={"Content-Type": "application/octet-stream"})


def casos(pid):
    return client.get(f"/api/test-cases/?project_id={pid}").json()


# ------------------------------------------------------------------------------------------- plantilla

def test_plantilla_es_un_xlsx_real_con_instrucciones_y_lista_de_validaciones():
    r = client.get("/api/excel/template")
    assert r.status_code == 200 and r.headers["content-type"] == excel_io.XLSX_MEDIA_TYPE
    assert "plantilla_casos.xlsx" in r.headers["content-disposition"]
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Casos", "Instrucciones"]
    assert [c.value for c in wb["Casos"][1]] == HEADERS
    listas = [dv.formula1 for dv in wb["Casos"].data_validations.dataValidation]
    assert any("ROW_COUNT,SCALAR_VALUE,EXISTS" in f for f in listas)
    assert "SCALAR_VALUE" in " ".join(str(c.value) for c in wb["Instrucciones"]["A"])


def test_la_plantilla_descargada_se_puede_importar_tal_cual():
    pid = proyecto()
    res = importar(pid, client.get("/api/excel/template").content)
    assert res.status_code == 200 and res.json()["ok"] is True and res.json()["n_crear"] == 3


# ------------------------------------------------------------------------------------------- importar

def test_importar_crea_casos_normaliza_valores_y_crea_suites():
    pid = proyecto()
    res = importar(pid, xlsx(OK_ROWS))
    body = res.json()
    assert res.status_code == 200 and body["ok"] and body["importado"] and body["n_crear"] == 4

    por_nombre = {c["name"]: c for c in casos(pid)}
    assert por_nombre["Hay 5 productos"]["validation_type"] == "SCALAR_VALUE" and por_nombre["Hay 5 productos"]["expected_result"] == "5"   # 5.0 -> "5"
    assert por_nombre["Sin nombres vacíos"]["validation_type"] == "SCALAR_VALUE"        # alias «valor»
    assert por_nombre["Existe el ID 3"]["expected_result"] == "true"                    # TRUE de Excel -> "true"
    assert por_nombre["Filas devueltas"]["validation_type"] == "ROW_COUNT"             # alias «cantidad de filas»

    suites = {s["name"]: s for s in client.get(f"/api/suites/?project_id={pid}").json()}
    assert set(suites) == {"Reglas", "Extra"} and body["suites_creadas"] == 2
    assert len(client.get(f"/api/suites/{suites['Reglas']['id']}").json()["test_cases"]) == 2


def test_simulacion_no_guarda_nada():
    pid = proyecto()
    res = importar(pid, xlsx(OK_ROWS), dry_run=True)
    assert res.json()["ok"] and res.json()["simulacion"] and not res.json()["importado"] and res.json()["n_crear"] == 4
    assert casos(pid) == [] and client.get(f"/api/suites/?project_id={pid}").json() == []


def test_existentes_se_omiten_o_se_actualizan_segun_el_modo():
    pid = proyecto()
    importar(pid, xlsx(OK_ROWS))
    cambiado = [list(r) for r in OK_ROWS]
    cambiado[0][4] = 99
    omitir = importar(pid, xlsx(cambiado), mode="skip").json()
    assert omitir["n_omitidos"] == 4 and omitir["n_crear"] == 0
    assert {c["name"]: c["expected_result"] for c in casos(pid)}["Hay 5 productos"] == "5"
    actualizar = importar(pid, xlsx(cambiado), mode="update").json()
    assert actualizar["n_actualizar"] == 4 and len(casos(pid)) == 4
    assert {c["name"]: c["expected_result"] for c in casos(pid)}["Hay 5 productos"] == "99"


FILA_BASE = ["Caso", "d", "SELECT 1 FROM DUAL", "ROW_COUNT", 1, None]


def fila(**cambios):
    idx = {"nombre": 0, "descripcion": 1, "sql": 2, "validacion": 3, "esperado": 4, "suites": 5}
    r = list(FILA_BASE)
    for k, v in cambios.items():
        r[idx[k]] = v
    return r


@pytest.mark.parametrize("fila_mala,campo,texto", [
    (fila(nombre=None), "Nombre", "obligatorio"),
    (fila(sql=None), "SQL", "obligatorio"),
    (fila(sql="DROP TABLE FRAMEWORK_TEST_ITEMS"), "SQL", "Rechazado"),
    (fila(sql="TRUNCATE TABLE FRAMEWORK_TEST_ITEMS"), "SQL", "Rechazado"),
    (fila(sql="SELECT 1 FROM DUAL; DELETE FROM FRAMEWORK_TEST_ITEMS"), "SQL", "múltiples sentencias"),
    (fila(validacion=None), "Validación", "obligatoria"),
    (fila(validacion="MUCHAS"), "Validación", "no es válida"),
    (fila(esperado=None), "Esperado", "obligatorio"),
    (fila(esperado="abc"), "Esperado", "ROW_COUNT"),
    (fila(esperado=-1), "Esperado", "ROW_COUNT"),
    (fila(validacion="EXISTS", esperado="quizas"), "Esperado", "true"),
    (fila(validacion="SCALAR_VALUE", sql="INSERT INTO FRAMEWORK_TEST_ITEMS VALUES (9, 'x', 1)", esperado=1), "Validación", "SELECT"),
    (fila(descripcion="x" * 501), "Descripción", "500"),
    (fila(nombre="n" * 151), "Nombre", "150"),
    (fila(suites="a;b;c;d;e;f"), "Suites", "5"),
    (fila(sql="=cmd|' /C calc'!A0"), "SQL", "fórmulas"),
])
def test_validaciones_rechazan_la_fila_y_no_se_importa_nada(fila_mala, campo, texto):
    pid = proyecto()
    res = importar(pid, xlsx([OK_ROWS[0], fila_mala]))      # una fila buena + una mala: todo o nada
    body = res.json()
    assert res.status_code == 200 and body["ok"] is False and body["importado"] is False
    err = [e for e in body["errores"] if e["fila"] == 3][0]
    assert err["campo"] == campo and texto in err["mensaje"]
    assert casos(pid) == [], "con un error no se debe importar ni la fila válida"


def test_nombres_repetidos_en_el_archivo_se_reportan_con_la_fila():
    body = importar(proyecto(), xlsx([fila(), fila()])).json()
    assert body["ok"] is False and "repetido en el archivo" in body["errores"][0]["mensaje"] and "fila 2" in body["errores"][0]["mensaje"]


def test_celdas_con_formula_real_se_rechazan():
    wb = Workbook()
    ws = wb.active
    ws.title = "Casos"
    ws.append(HEADERS)
    ws.append(["F", "", "SELECT 1 FROM DUAL", "ROW_COUNT", "=1+1", None])      # openpyxl lo guarda como fórmula
    buf = io.BytesIO()
    wb.save(buf)
    body = importar(proyecto(), buf.getvalue()).json()
    assert body["ok"] is False and "fórmulas" in body["errores"][0]["mensaje"]


def test_filas_vacias_se_ignoran_y_los_encabezados_aceptan_variantes():
    pid = proyecto()
    contenido = xlsx([[None] * 6, fila(nombre="Solo uno"), [None] * 6], headers=["nombre", "descripcion", "sql", "validacion", "esperado", "suites"])
    assert importar(pid, contenido).json()["n_crear"] == 1


# --------------------------------------------------------------------------- archivos inválidos (conjunto)

def test_archivos_invalidos_se_rechazan_con_un_mensaje_claro():
    pid = proyecto()
    assert importar(pid, b"nombre,sql\nx,SELECT 1").status_code == 422                     # CSV
    assert importar(pid, b"").status_code == 422                                           # vacío
    assert importar(pid, b"PK\x03\x04basura").status_code == 422                           # zip dañado
    assert importar(pid, xlsx([fila()], sheet="Otra hoja")).status_code == 422             # falta la hoja «Casos»
    sin_col = importar(pid, xlsx([["a"]], headers=["Nombre"]))
    assert sin_col.status_code == 422 and "Faltan columnas obligatorias" in sin_col.json()["detail"]
    assert importar(pid, xlsx([])).status_code == 422                                      # sin filas con datos
    assert casos(pid) == []


def test_archivo_con_macros_o_demasiado_grande_se_rechaza():
    pid = proyecto()
    base = xlsx([fila()])
    buf = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(base)) as zin, zipfile.ZipFile(buf, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("xl/vbaProject.bin", b"macro")
    macros = importar(pid, buf.getvalue())
    assert macros.status_code == 422 and "macros" in macros.json()["detail"]

    grande = importar(pid, b"PK" + b"0" * (excel_io.MAX_BYTES + 10))
    assert grande.status_code in (413, 422)
    assert casos(pid) == []


def test_proyecto_inexistente_y_modo_invalido():
    assert importar(9999, xlsx([fila()])).status_code == 404
    assert importar(proyecto(), xlsx([fila()]), mode="borrar").status_code == 422


# ------------------------------------------------------------------------------------------- exportar

def test_exportar_casos_y_reimportarlos_en_otro_proyecto_es_un_ciclo_completo():
    origen, destino = proyecto("Origen"), proyecto("Destino")
    importar(origen, xlsx(OK_ROWS))
    exp = client.get(f"/api/excel/cases/export?project_id={origen}")
    assert exp.status_code == 200 and exp.headers["content-type"] == excel_io.XLSX_MEDIA_TYPE
    ws = load_workbook(io.BytesIO(exp.content))["Casos"]
    assert ws.max_row == 5 and [c.value for c in ws[1]] == HEADERS
    assert {ws.cell(row=r, column=6).value for r in range(2, 6)} >= {"Reglas", "Extra; Reglas"}

    res = importar(destino, exp.content).json()
    assert res["ok"] and res["n_crear"] == 4
    assert {c["name"]: (c["validation_type"], c["expected_result"]) for c in casos(destino)} == \
           {c["name"]: (c["validation_type"], c["expected_result"]) for c in casos(origen)}


def test_el_texto_que_parece_formula_se_exporta_como_texto_literal():
    pid = proyecto()
    for nombre in ("=HYPERLINK(\"http://x\")", "+1+1", "-2+3", "@SUM(A1)"):
        client.post("/api/test-cases/", json={"project_id": pid, "name": nombre, "sql_query": "SELECT 1 FROM DUAL", "expected_result": "1"})
    wb = load_workbook(io.BytesIO(client.get(f"/api/excel/cases/export?project_id={pid}").content))
    ws = wb["Casos"]
    for r in range(2, 6):
        celda = ws.cell(row=r, column=1)
        assert celda.data_type == "s", f"{celda.value!r} no debe ser una fórmula"
    assert ws["A2"].value == "=HYPERLINK(\"http://x\")"


def test_exportar_resultados_con_colores_filtros_y_resumen():
    pid = proyecto()
    db = next(app.dependency_overrides[get_db]())
    for estado, esperado, obtenido in (("PASS", "1", "[[1]]"), ("FAIL", "5", "[[1]]"), ("ERROR", "1", None)):
        db.add(ExecutionHistory(project_id=pid, status=estado, duration_ms=3.5, executed_sql="SELECT 1 FROM DUAL", expected_result=esperado,
                                actual_result=obtenido, validation_type="ROW_COUNT", trigger_source="CLI", run_id="r1",
                                error_message="ORA-00942" if estado == "ERROR" else None))
    db.commit()

    r = client.get(f"/api/excel/results/export?project_id={pid}")
    wb = load_workbook(io.BytesIO(r.content))
    assert wb.sheetnames == ["Resultados", "Resumen"]
    ws = wb["Resultados"]
    assert ws.max_row == 4
    estados = {ws.cell(row=i, column=6).value: ws.cell(row=i, column=6).fill.fgColor.rgb for i in range(2, 5)}
    assert estados["PASS"].endswith("C6EFCE") and estados["FAIL"].endswith("FFEB9C") and estados["ERROR"].endswith("FFC7CE")
    assert ws.cell(row=2, column=12).value == "CLI"
    resumen = {wb["Resumen"].cell(row=i, column=1).value: wb["Resumen"].cell(row=i, column=2).value for i in range(1, 6)}
    assert resumen["Filas exportadas"] == 3 and (resumen["PASS"], resumen["FAIL"], resumen["ERROR"]) == (1, 1, 1)

    solo_fail = load_workbook(io.BytesIO(client.get(f"/api/excel/results/export?project_id={pid}&status=FAIL").content))["Resultados"]
    assert solo_fail.max_row == 2
    assert client.get("/api/excel/results/export?status=OTRO").status_code == 422
    assert client.get("/api/excel/results/export?project_id=9999").status_code == 404


def test_exportar_resultados_sin_datos_genera_un_libro_valido_con_cero_filas():
    wb = load_workbook(io.BytesIO(client.get("/api/excel/results/export").content))
    assert wb["Resultados"].max_row == 1 and wb["Resumen"]["B2"].value == 0


def test_el_uso_de_excel_queda_registrado_para_el_dashboard():
    pid = proyecto()
    importar(pid, xlsx(OK_ROWS), dry_run=True)
    importar(pid, xlsx(OK_ROWS))
    client.get(f"/api/excel/cases/export?project_id={pid}")
    client.get("/api/excel/results/export?project_id=%d" % pid)
    client.get("/api/excel/template")
    eventos = {e["tipo"]: e["cantidad"] for e in client.get(f"/api/usage/summary?days=7&project_id={pid}").json()["eventos"]}
    assert eventos == {"excel_validate_cases": 1, "excel_import_cases": 1, "excel_export_cases": 1, "excel_export_results": 1}


def test_los_botones_de_excel_existen_en_la_interfaz():
    from pathlib import Path
    html = Path("frontend/index.html").read_text(encoding="utf-8")
    app_js = Path("frontend/app.js").read_text(encoding="utf-8")
    for boton in ("btn-plantilla-excel", "btn-importar-excel", "btn-exportar-casos", "btn-exportar-resultados"):
        assert f'id="{boton}"' in html and boton in app_js
    js = Path("frontend/js/modulos/excel.js").read_text(encoding="utf-8")
    assert "dry_run=${soloValidar}" in js and "application/octet-stream" in js
