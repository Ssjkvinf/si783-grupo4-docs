"""
Escenario de demostración: reglas de calidad de datos sobre la tabla FRAMEWORK_TEST_ITEMS.

La tabla la crea infra/oracle/init/001_test_schema.sh (columnas ID, NAME, ACTIVE) y los datos
de ejemplo los carga infra/oracle/demo/seed_demo_data.sql en un Oracle local desechable.
Aquí solo se definen CASOS DE PRUEBA y SUITES en la base interna; no se toca Oracle.

Valores esperados (coinciden con los datos del script de carga: 5 productos, 4 activos):
"""
from typing import Dict, List
from sqlalchemy.orm import Session

from app.models import test_case as models_tc
from app.models import suite as models_suite

RULES_SUITE_NAME = "Demo: reglas de calidad de FRAMEWORK_TEST_ITEMS"
EXAMPLES_SUITE_NAME = "Demo: ejemplos de FAIL y ERROR (intencionales)"

# (nombre, descripción, sql, validación, esperado)
RULES_CASES = [
    ("Hay 5 productos registrados",
     "Cantidad esperada de registros: el valor que calcula COUNT(*) debe ser 5.",
     "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", "5"),
    ("No hay productos sin nombre",
     "Ausencia de datos inválidos: 0 registros con NAME vacío o en blanco.",
     "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS WHERE TRIM(NAME) IS NULL", "SCALAR_VALUE", "0"),
    ("ACTIVE solo vale 0 o 1",
     "Ausencia de datos inválidos: 0 registros con ACTIVE distinto de 0 y 1.",
     "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS WHERE ACTIVE NOT IN (0, 1)", "SCALAR_VALUE", "0"),
    ("Hay 4 productos activos",
     "El valor que calcula COUNT(*) sobre los registros con ACTIVE = 1 debe ser 4.",
     "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS WHERE ACTIVE = 1", "SCALAR_VALUE", "4"),
    ("Existe el producto con ID 3",
     "Existencia de un registro: la consulta debe devolver al menos una fila.",
     "SELECT ID, NAME FROM FRAMEWORK_TEST_ITEMS WHERE ID = 3", "EXISTS", "true"),
]

EXAMPLES_CASES = [
    ("FAIL de ejemplo: se esperan 6 productos (hay 5)",
     "Se ejecuta bien pero el valor no coincide: sirve para ver un FAIL.",
     "SELECT COUNT(*) FROM FRAMEWORK_TEST_ITEMS", "SCALAR_VALUE", "6"),
    ("ERROR de ejemplo: tabla inexistente",
     "La consulta no puede ejecutarse (ORA-00942): sirve para ver un ERROR.",
     "SELECT COUNT(*) FROM TABLA_QUE_NO_EXISTE", "SCALAR_VALUE", "0"),
]


def _ensure_suite(db: Session, project_id: int, suite_name: str, cases: List[tuple]) -> Dict:
    created_cases = 0
    case_objs = []
    for name, desc, sql, val, exp in cases:
        tc = db.query(models_tc.TestCase).filter(
            models_tc.TestCase.project_id == project_id, models_tc.TestCase.name == name).first()
        if tc is None:
            tc = models_tc.TestCase(project_id=project_id, name=name, description=desc,
                                    sql_query=sql, validation_type=val, expected_result=exp)
            db.add(tc)
            created_cases += 1
        case_objs.append(tc)
    db.flush()

    suite = db.query(models_suite.TestSuite).filter(
        models_suite.TestSuite.project_id == project_id, models_suite.TestSuite.name == suite_name).first()
    created_suite = suite is None
    if suite is None:
        suite = models_suite.TestSuite(project_id=project_id, name=suite_name,
                                       description="Escenario de demostración (ver docs/demostracion-fase2.md).")
        db.add(suite)
        db.flush()
    for tc in case_objs:
        if tc not in suite.test_cases:
            suite.test_cases.append(tc)
    return {"suite_id": suite.id, "suite_name": suite.name, "case_ids": [c.id for c in case_objs],
            "created_suite": created_suite, "created_cases": created_cases}


def load_demo_scenario(db: Session, project_id: int) -> Dict:
    """Crea (si faltan) los casos y las dos suites de demostración. Es idempotente."""
    rules = _ensure_suite(db, project_id, RULES_SUITE_NAME, RULES_CASES)
    examples = _ensure_suite(db, project_id, EXAMPLES_SUITE_NAME, EXAMPLES_CASES)
    db.commit()
    return {"project_id": project_id, "rules_suite": rules, "examples_suite": examples}
