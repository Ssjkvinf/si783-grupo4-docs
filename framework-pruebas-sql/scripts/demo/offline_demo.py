#!/usr/bin/env python3
"""
Demostración SIN Oracle (ruta alternativa si falla Docker, la red o el Oracle desechable).

*** MODO SIMULADO: NO ES ORACLE. ***
Usa una base SQLite con la tabla FRAMEWORK_TEST_ITEMS detrás de la interfaz de `oracledb.connect`
(tests/fake_oracle.py). Ejecuta SQL real sobre SQLite, no sobre Oracle: sirve para mostrar el flujo
de la aplicación, no para demostrar el comportamiento de Oracle (rollback, privilegios, DDL).
Todo se guarda en una carpeta temporal (no toca ninguna base real ni el repositorio).

Uso (desde framework-pruebas-sql/):
  python scripts/demo/offline_demo.py servir [--puerto 8001]   prepara los datos y levanta la aplicación
  python scripts/demo/offline_demo.py romper                   deja ACTIVE=7 en el producto 4 (provoca 1 FAIL)
  python scripts/demo/offline_demo.py reparar                  restaura los datos de demostración
  python scripts/demo/offline_demo.py ruta                     muestra la carpeta de trabajo

En la interfaz: el perfil «SIMULADO (no es Oracle)» acepta cualquier contraseña distinta de «mala».
No hay secretos: no se pide ni se guarda ninguna credencial real.
"""
import argparse
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(tempfile.gettempdir()) / "framework_demo_offline"
INTERNAL = WORK / "interna.sqlite"
TARGET = WORK / "objetivo_simulado.sqlite"
BANNER = "*** MODO SIMULADO: NO ES ORACLE. SQLite detrás de la interfaz de oracledb. Solo para mostrar el flujo. ***"


def _preparar_objetivo(reparar: bool = False) -> None:
    sys.path.insert(0, str(ROOT / "tests"))
    from fake_oracle import make_database
    WORK.mkdir(parents=True, exist_ok=True)
    if reparar and TARGET.exists():
        TARGET.unlink()
    if not TARGET.exists():
        make_database(TARGET)


def cmd_romper() -> int:
    _preparar_objetivo()
    con = sqlite3.connect(str(TARGET))
    con.execute("UPDATE FRAMEWORK_TEST_ITEMS SET ACTIVE = 7 WHERE ID = 4")
    con.commit()
    con.close()
    print("Dato roto: producto 4 con ACTIVE=7 (la regla «ACTIVE solo vale 0 o 1» dará FAIL).")
    return 0


def cmd_reparar() -> int:
    _preparar_objetivo(reparar=True)
    print("Datos de demostración restaurados (5 productos, 4 activos).")
    return 0


def cmd_servir(puerto: int) -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    os.environ["FRAMEWORK_DB_URL"] = "sqlite:///" + INTERNAL.as_posix()
    os.environ["APP_ACCESS_ENABLED"] = "false"
    sys.path.insert(0, str(ROOT))
    _preparar_objetivo()

    from alembic import command
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(cfg, "head")

    import oracledb
    sys.path.insert(0, str(ROOT / "tests"))
    from fake_oracle import connect_factory
    oracledb.connect = connect_factory(str(TARGET))

    from app.core.database import SessionLocal
    from app.models import project, connection, test_case, suite, history, usage  # noqa: F401
    from app.services.demo_scenario import load_demo_scenario
    db = SessionLocal()
    try:
        proy = db.query(project.Project).filter(project.Project.name == "Demo simulado").first()
        if not proy:
            proy = project.Project(name="Demo simulado", description="Datos simulados: NO es Oracle")
            db.add(proy)
            db.commit()
            db.refresh(proy)
        if not db.query(connection.ConnectionProfile).filter(connection.ConnectionProfile.project_id == proy.id).first():
            db.add(connection.ConnectionProfile(project_id=proy.id, name="SIMULADO (no es Oracle)", host="simulado.local", port=1521,
                                                service_name="SIMULADO", username="FRAMEWORK_TEST", environment_type="TEST"))
            db.commit()
        load_demo_scenario(db, proy.id)
    finally:
        db.close()

    print(BANNER)
    print(f"Carpeta de trabajo: {WORK}")
    print(f"Abra http://127.0.0.1:{puerto}/ui/  (proyecto «Demo simulado», conexión «SIMULADO»; contraseña: cualquiera salvo «mala»)")
    import uvicorn
    from app.main import app
    uvicorn.run(app, host="127.0.0.1", port=puerto, log_level="warning")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("servir")
    s.add_argument("--puerto", type=int, default=8001)
    sub.add_parser("romper")
    sub.add_parser("reparar")
    sub.add_parser("ruta")
    a = ap.parse_args(argv)
    if a.cmd == "servir":
        return cmd_servir(a.puerto)
    if a.cmd == "romper":
        return cmd_romper()
    if a.cmd == "reparar":
        return cmd_reparar()
    print(WORK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
