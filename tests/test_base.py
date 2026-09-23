"""Solidez de la base: integridad, esquema al día, migraciones, datos independientes de la interfaz y copias."""
import ast
import sqlite3
from pathlib import Path

import models
from db import arqueos, backup, connection

from tests import BASE_REAL, BaseTemporal

RAIZ = Path(__file__).resolve().parent.parent

# tabla de cada definición de campos de models.py
TABLAS = {"accesorios": models.ACCESORIOS, "equipos": models.EQUIPOS, "casim": models.CASIM, "cater": models.CATER,
          "regular": models.REGULAR, "porta": models.PORTA, "baf": models.BAF, "gastos": models.GASTOS,
          "planes": models.PLANES, "planes_baf": models.PLANES_BAF, "descuentos": models.DESCUENTOS,
          "tareas": models.TAREAS, "cierres": models.CIERRES, "sucursales": models.SUCURSALES,
          "empleados": models.EMPLEADOS, "cuentas": models.CUENTAS, "mov_accesorios": models.MOV_ACCESORIOS,
          "mov_equipos": models.MOV_EQUIPOS}


def columnas(db, tabla):
    return {r[1]: r for r in db.execute(f"PRAGMA table_info({tabla})")}


class EsquemaBaseNueva(BaseTemporal):
    def test_cada_campo_de_models_es_una_columna(self):
        for tabla, fields in TABLAS.items():
            cols = columnas(self.db, tabla)
            for f in fields:
                if f.kind not in ("multi", "pagos", "calc"):
                    self.assertIn(f.key, cols, f"{tabla}.{f.key}")
            self.assertIn("activo", cols, tabla)   # todas las bajas son lógicas

    def test_nace_en_la_ultima_version(self):
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], len(connection.MIGRACIONES))

    def test_un_solo_archivo_y_claves_foraneas(self):
        self.assertEqual(self.db.execute("PRAGMA journal_mode").fetchone()[0], "delete")
        self.assertEqual(self.db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db:
                self.db.execute("INSERT INTO gastos (detalle, monto, cuenta_id) VALUES ('X', 1, 999)")


class BaseReal(BaseTemporal):
    """Sobre una copia de data/nodo.db."""
    copia_real = True

    def test_integridad(self):
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(self.db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_version_al_dia(self):
        self.assertEqual(self.db.execute("PRAGMA user_version").fetchone()[0], len(connection.MIGRACIONES))

    def test_mismo_esquema_que_una_base_nueva(self):
        """La base real (que pasó por migraciones) tiene las mismas tablas y columnas que una creada de cero."""
        nueva = sqlite3.connect(":memory:")
        self.addCleanup(nueva.close)
        nueva.executescript(connection.SCHEMA)
        tablas = lambda db: {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        self.assertEqual(tablas(self.db) - {"sqlite_sequence"}, tablas(nueva) - {"sqlite_sequence"})
        for t in tablas(nueva) - {"sqlite_sequence"}:
            real = {k: (v[2], v[3]) for k, v in columnas(self.db, t).items()}      # tipo y NOT NULL
            limpia = {k: (v[2], v[3]) for k, v in columnas(nueva, t).items()}
            self.assertEqual(real, limpia, t)

    def test_migrar_de_nuevo_no_cambia_nada(self):
        antes = self.db.execute("SELECT COUNT(*) FROM gastos").fetchone()[0]
        for m in connection.MIGRACIONES:
            if m.__name__.startswith(("_m8", "_m9")):   # las que se pueden repetir sin daño
                with self.db:
                    m(self.db)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM gastos").fetchone()[0], antes)

    def test_m9_rehace_pagos_sin_perder_filas(self):
        """Simula una base vieja (pagos con cuenta opcional y datos) y la pasa por la migración 9."""
        cuenta = self.db.execute("SELECT id FROM cuentas LIMIT 1").fetchone()[0]
        with self.db:
            self.db.execute("DROP TABLE pagos")
            self.db.execute("CREATE TABLE pagos (id INTEGER PRIMARY KEY AUTOINCREMENT, origen TEXT NOT NULL, "
                            "mov_id INTEGER NOT NULL, monto REAL NOT NULL, cuenta_id INTEGER REFERENCES cuentas(id), "
                            "interes REAL NOT NULL DEFAULT 0)")
            self.db.executemany("INSERT INTO pagos (origen, mov_id, monto, cuenta_id, interes) VALUES (?, ?, ?, ?, ?)",
                                [("ventas", i, 100.5 * i, cuenta, i % 3) for i in range(1, 51)])
            connection._m9_pagos_con_cuenta_obligatoria(self.db)
        self.assertEqual(self.db.execute("SELECT COUNT(*), TOTAL(monto), TOTAL(interes) FROM pagos").fetchone()[:],
                         (50, sum(100.5 * i for i in range(1, 51)), sum(i % 3 for i in range(1, 51))))
        self.assertEqual(columnas(self.db, "pagos")["cuenta_id"][3], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO pagos (origen, mov_id, monto) VALUES ('ventas', 1, 1)")
        self.db.rollback()

    def test_m9_no_avanza_si_hay_pagos_sin_cuenta(self):
        with self.db:
            self.db.execute("DROP TABLE pagos")
            self.db.execute("CREATE TABLE pagos (id INTEGER PRIMARY KEY, origen TEXT, mov_id INTEGER, monto REAL, "
                            "cuenta_id INTEGER, interes REAL DEFAULT 0)")
            self.db.execute("INSERT INTO pagos (origen, mov_id, monto) VALUES ('ventas', 1, 10)")
        with self.assertRaises(RuntimeError):
            connection._m9_pagos_con_cuenta_obligatoria(self.db)
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM pagos").fetchone()[0], 1)

    def test_stock_de_accesorios_igual_a_sus_movimientos(self):
        """El stock guardado es la suma de los movimientos activos (así se cargó el stock inicial)."""
        diferencias = self.db.execute(
            "SELECT a.codigo, a.stock, COALESCE(SUM(CASE m.tipo WHEN 'VENTA' THEN -m.cantidad ELSE m.cantidad END), 0) AS movs "
            "FROM accesorios a LEFT JOIN mov_accesorios m ON m.producto_id = a.id AND m.activo = 1 "
            "WHERE a.activo = 1 AND a.virtual = 0 GROUP BY a.id HAVING a.stock <> movs").fetchall()
        self.assertEqual([tuple(r) for r in diferencias], [])

    def test_sin_referencias_a_registros_dados_de_baja_en_operaciones_vivas(self):
        malas = self.db.execute(
            "SELECT 'casim', g.id FROM casim g JOIN mov_equipos m ON m.id = g.mov_id WHERE g.activo = 1 AND m.activo = 0 "
            "UNION ALL SELECT 'cater', g.id FROM cater g JOIN mov_equipos m ON m.id = g.mov_id WHERE g.activo = 1 AND m.activo = 0 "
            "UNION ALL SELECT 'pagos', p.id FROM pagos p LEFT JOIN ventas v ON v.id = p.mov_id "
            "WHERE p.origen = 'ventas' AND (v.id IS NULL OR v.activo = 0)").fetchall()
        self.assertEqual([tuple(r) for r in malas], [])

    def test_arqueos_encadenados(self):
        rows = arqueos.listar()
        self.assertTrue(rows)
        self.assertAlmostEqual(sum(r["variacion"] for r in rows), rows[0]["resultado"], places=2)
        for r in rows:
            self.assertAlmostEqual(r["resultado"], r["cf_val"] + r["cc_val"] - r["sc_val"], places=2)
            self.assertTrue(r["empleados"], r["fecha"])

    def test_fechas_con_formato_de_la_base(self):
        for tabla in ("gastos", "casim", "cater", "regular", "porta", "baf", "ventas", "mov_accesorios",
                      "mov_equipos", "arqueos", "tareas"):
            malas = self.db.execute(f"SELECT id, fecha FROM {tabla} WHERE fecha NOT GLOB "
                                    "'[0-9][0-9][0-9][0-9]-[0-1][0-9]-[0-3][0-9]*'").fetchall()
            self.assertEqual([tuple(r) for r in malas], [], tabla)

    def test_copia_de_seguridad_identica(self):
        destino = self.path.with_name("copia.db")
        backup.copiar(destino)
        copia = sqlite3.connect(destino)
        for t in ("gastos", "arqueos", "baf", "mov_accesorios", "casim"):
            q = f"SELECT COUNT(*), TOTAL(id) FROM {t}"
            self.assertEqual(copia.execute(q).fetchone(), tuple(self.db.execute(q).fetchone()), t)
        copia.close()


class DatosSeparadosDeLaInterfaz(BaseTemporal):
    """Un cambio de estética (ui/) no puede tocar los datos: db/ y models.py no dependen de tkinter ni de ui/."""

    def test_db_no_importa_la_interfaz(self):
        for archivo in [RAIZ / "models.py", *sorted((RAIZ / "db").glob("*.py"))]:
            arbol = ast.parse(archivo.read_text(encoding="utf-8"))
            # solo los imports de primer nivel: los que están dentro de una función (p. ej. arqueos.etiqueta) no se
            # cargan al abrir la base
            modulos = [n.module if isinstance(n, ast.ImportFrom) else a.name
                       for n in arbol.body if isinstance(n, (ast.Import, ast.ImportFrom))
                       for a in (n.names if isinstance(n, ast.Import) else [n])]
            for m in modulos:
                if m == "ui.formatting":   # permitido: funciones puras, fijadas en test_formato_de_los_datos
                    continue
                self.assertFalse((m or "").startswith(("tkinter", "ui")), f"{archivo.name} importa {m}")

    def test_formatting_es_puro(self):
        """ui/formatting.py lo usa también db/importer.py: no puede depender de la interfaz."""
        arbol = ast.parse((RAIZ / "ui" / "formatting.py").read_text(encoding="utf-8"))
        modulos = {a.name for n in arbol.body if isinstance(n, ast.Import) for a in n.names} |                   {n.module for n in arbol.body if isinstance(n, ast.ImportFrom)}
        self.assertLessEqual(modulos, {"re", "datetime"})

    def test_formato_de_los_datos(self):
        """Cómo se leen y se guardan montos y fechas (CSV y formularios). Si un cambio visual rompe esto, falla acá."""
        from ui.formatting import money_to_input, parse_date, parse_datetime, parse_int, parse_money
        casos = {"1.234,56": 1234.56, "1234,56": 1234.56, "1234.56": 1234.56, "1.500": 1500.0, "$ 2.000,5": 2000.5,
                 "": 0.0, "0,1": 0.1}
        for texto, valor in casos.items():
            self.assertEqual(parse_money(texto), valor, texto)
        for valor in (0.0, 0.1, 1234.56, 1500.0, 99999999.99):
            self.assertEqual(parse_money(money_to_input(valor)), valor)
        for malo in ("abc", "1,2,3", "12a"):
            with self.assertRaises(ValueError):
                parse_money(malo)
        self.assertEqual((parse_int("1.500"), parse_int("-3", signed=True)), (1500, -3))
        self.assertEqual(parse_date("19/09/2026"), "2026-09-19")
        self.assertEqual(parse_datetime("19/09/2026 15:11"), "2026-09-19 15:11:00")

    def test_ui_no_escribe_sql(self):
        """Las pantallas usan los repos: si una pantalla escribe en la base, un cambio visual podría romper datos."""
        for archivo in sorted((RAIZ / "ui").rglob("*.py")):
            texto = archivo.read_text(encoding="utf-8").upper()
            for sql in ("INSERT INTO", "UPDATE ", "DELETE FROM", "ALTER TABLE", "DROP TABLE"):
                self.assertNotIn(sql, texto.replace("UPDATE_", "").replace("_UPDATE", ""), f"{archivo.name}: {sql}")
