"""Tests de Nodo. Correr desde la carpeta del proyecto:  .venv\\Scripts\\python -m unittest -v

Nunca tocan data/nodo.db: cada test trabaja sobre una base temporal (vacía o copia de la real) vía NODO_DB.
"""
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path

from db import connection

BASE_REAL = connection.DEFAULT_PATH


def _reset():
    if connection._conn is not None:
        connection._conn.close()
    connection._conn = None


class BaseTemporal(unittest.TestCase):
    """Cada test arranca con una base nueva y vacía (o con una copia de la real si `copia_real`)."""
    copia_real = False

    def setUp(self):
        self._dir = tempfile.mkdtemp(prefix="nodo_test_")
        self.path = Path(self._dir) / "nodo.db"
        if self.copia_real:
            if not BASE_REAL.exists():
                self.skipTest("no hay data/nodo.db")
            origen = sqlite3.connect(f"file:{BASE_REAL}?mode=ro", uri=True)   # copia consistente aunque la app esté abierta
            destino = sqlite3.connect(self.path)
            origen.backup(destino)
            origen.close()
            destino.close()
        self._env = os.environ.get("NODO_DB")
        os.environ["NODO_DB"] = str(self.path)
        _reset()
        self.db = connection.get()

    def tearDown(self):
        _reset()
        if self._env is None:
            os.environ.pop("NODO_DB", None)
        else:
            os.environ["NODO_DB"] = self._env
        shutil.rmtree(self._dir, ignore_errors=True)

    # --- datos mínimos para operar ---------------------------------------
    def sembrar(self):
        db = self.db
        with db:
            self.suc = db.execute("INSERT INTO sucursales (codigo, nombre) VALUES ('L002', '3ROSARIO')").lastrowid
            self.emp = db.execute("INSERT INTO empleados (nombre) VALUES ('AMADORI, ENZO')").lastrowid
            self.efe = db.execute("INSERT INTO cuentas (codigo, tipo, descripcion) VALUES ('EFE', 'EFECTIVO', 'EFECTIVO')").lastrowid
            self.visa = db.execute("INSERT INTO cuentas (codigo, tipo, descripcion) VALUES ('VISA', 'TARJETA', 'VISA')").lastrowid
            self.fin = db.execute("INSERT INTO cuentas (codigo, tipo, descripcion) VALUES ('FINANCIADO', 'CLARO', 'FINANCIADO')").lastrowid
            self.funda = db.execute("INSERT INTO accesorios (codigo, descripcion, stock) VALUES ('F1', 'FUNDA', 10)").lastrowid
            self.cargador = db.execute("INSERT INTO accesorios (codigo, descripcion, stock) VALUES ('C1', 'CARGADOR', 5)").lastrowid
            self.sim = db.execute("INSERT INTO equipos (codigo, descripcion, marca, stock) VALUES ('SIM', 'USIM', 'SIM', 100)").lastrowid
            self.celu = db.execute("INSERT INTO equipos (codigo, descripcion, marca, stock) VALUES ('A15', 'GALAXY A15', 'SAMSUNG', 3)").lastrowid

    def stock(self, tabla, producto_id):
        return self.db.execute(f"SELECT stock FROM {tabla} WHERE id = ?", (producto_id,)).fetchone()[0]
