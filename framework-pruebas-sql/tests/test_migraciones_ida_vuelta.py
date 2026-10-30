"""
Migraciones de ida y vuelta sobre una SQLite desechable: head -> base -> head, y la de usuarios (a4b8c2d9e1f0) -1 / +1.
Antes, bajar la migración 001 fallaba al quitar claves foráneas que SQLite no tiene con nombre.
"""
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _alembic(db, *args):
    env = dict(os.environ, FRAMEWORK_DB_URL=f"sqlite:///{db.as_posix()}")
    return subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=env, capture_output=True, text=True)


def _tablas(db):
    with sqlite3.connect(db) as con:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_head_base_head(tmp_path):
    db = tmp_path / "ida_vuelta.sqlite"
    assert _alembic(db, "upgrade", "head").returncode == 0
    r = _alembic(db, "downgrade", "base")
    assert r.returncode == 0, r.stderr[-800:]
    assert "users" not in _tablas(db) and "projects" not in _tablas(db)
    assert _alembic(db, "upgrade", "head").returncode == 0
    assert {"users", "projects", "execution_history"} <= _tablas(db)
    assert _alembic(db, "check").returncode == 0


def test_migracion_de_usuarios_baja_y_sube_conservando_el_historial(tmp_path):
    db = tmp_path / "usuarios.sqlite"
    assert _alembic(db, "upgrade", "head").returncode == 0
    with sqlite3.connect(db) as con:
        con.execute("INSERT INTO execution_history (project_id, status, duration_ms, executed_sql, executed_by) VALUES (1, 'PASS', 1, 'x', 'ana')")
    assert _alembic(db, "downgrade", "-1").returncode == 0
    assert "users" not in _tablas(db)
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM execution_history").fetchone()[0] == 1
        assert "executed_by" not in [r[1] for r in con.execute("PRAGMA table_info(execution_history)")]
    assert _alembic(db, "upgrade", "head").returncode == 0
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT executed_by FROM execution_history").fetchone()[0] is None
