"""Áreas: cada sucursal pertenece a un área (migración 10, listado, Datos por completar y CSV por nombre clave)."""
import csv

from db import administracion, connection, importer, pendientes

from tests import BaseTemporal, _reset


class Areas(BaseTemporal):
    def setUp(self):
        super().setUp()
        with self.db:
            self.ros = self.db.execute("INSERT INTO areas (codigo, nombre) VALUES ('ROS', 'ROSARIO')").lastrowid
            self.sfe = self.db.execute("INSERT INTO areas (codigo, nombre) VALUES ('SFE', 'SANTA FE')").lastrowid
            self.db.execute("INSERT INTO sucursales (codigo, nombre, area_id) VALUES ('L002', '3ROSARIO', ?)", (self.ros,))
            self.db.execute("INSERT INTO sucursales (codigo, nombre) VALUES ('L003', 'SIN AREA')")

    def csv(self, nombre, encabezado, filas):
        path = self.path.with_name(nombre)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(encabezado)
            w.writerows(filas)
        return path

    def test_listado_trae_el_area_y_filtra_por_ella(self):
        filas = {r["codigo"]: r for r in administracion.sucursales.list()}
        self.assertEqual((filas["L002"]["area_id_label"], filas["L003"]["area_id_label"]), ("ROS - ROSARIO", ""))
        self.assertEqual(administracion.sucursales.distinct("area_id"), ["ROS - ROSARIO"])
        self.assertEqual([r["codigo"] for r in administracion.sucursales.list("", "ROS - ROSARIO")], ["L002"])
        self.assertEqual([r["codigo"] for r in administracion.sucursales.list("santa")], [])
        self.assertEqual([r["codigo"] for r in administracion.sucursales.list("rosario")], ["L002"])

    def test_sucursal_sin_area_queda_por_completar(self):
        cat = next(c for c in pendientes.categorias() if c["clave"] == "sucursales")
        self.assertEqual([f["codigo"] for f in cat["filas"]], ["L003"])

    def test_csv_asigna_el_area_por_nombre_clave(self):
        path = self.csv("s.csv", ["Nombre clave", "Área", "Nombre"],
                        [["L003", "sfe", ""], ["L004", "ROS", "NUEVA"], ["L005", "XXX", "MALA"], ["L006", "", "SIN AREA"]])
        plan = importer.build_plan(administracion.sucursales, path)
        self.assertEqual([u["clave"] for u in plan.updates], ["L003"])
        self.assertEqual([i["clave"] for i in plan.inserts], ["L004"])
        self.assertEqual({clave: motivo for _, clave, motivo in plan.skipped},
                         {"L005": "Área: no existe el área XXX.", "L006": "Es nuevo, pero falta Área."})
        importer.apply_plan(administracion.sucursales, plan)
        areas = dict(self.db.execute("SELECT codigo, area_id FROM sucursales"))
        self.assertEqual((areas["L003"], areas["L004"]), (self.sfe, self.ros))

    def test_exportar_e_importar_es_identico(self):
        salida = self.path.with_name("export.csv")
        importer.export_csv(administracion.sucursales, salida)
        with open(salida, encoding="utf-8-sig") as fh:
            filas = list(csv.reader(fh, delimiter=";"))
        self.assertEqual([f[2] for f in filas], ["Área", "ROS", ""])   # el área sale por su nombre clave
        plan = importer.build_plan(administracion.sucursales, salida)
        self.assertEqual((len(plan.inserts), len(plan.updates), plan.unchanged), (0, 0, 2))


class Migracion10(BaseTemporal):
    def test_base_en_version_9_agrega_el_area_sin_perder_sucursales(self):
        """Simula una base anterior a las áreas: sucursales sin area_id y versión 9."""
        with self.db:
            self.db.execute("INSERT INTO sucursales (codigo, nombre) VALUES ('L002', '3ROSARIO')")
        self.db.execute("ALTER TABLE sucursales DROP COLUMN area_id")
        self.db.execute("PRAGMA user_version = 9")
        self.db.commit()
        _reset()
        db = connection.get()
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], len(connection.MIGRACIONES))
        self.assertEqual(db.execute("SELECT codigo, area_id FROM sucursales").fetchall()[0][:], ("L002", None))


class Migracion11(BaseTemporal):
    def test_direccion_en_una_casilla_y_celular_a_telefono(self):
        """Simula una base en versión 10: sucursales con entidad, calle, número, piso/depto. y celular aparte."""
        self.db.execute("ALTER TABLE sucursales DROP COLUMN direccion")
        for columna in ("entidad", "calle", "numero", "piso_depto", "celular"):
            self.db.execute(f"ALTER TABLE sucursales ADD COLUMN {columna} TEXT NOT NULL DEFAULT ''")
        self.db.executemany(
            "INSERT INTO sucursales (codigo, nombre, entidad, calle, numero, piso_depto, telefono, celular) "
            "VALUES (?, ?, 'CLARO', ?, ?, ?, ?, ?)",
            [("L001", "COMPLETA", "MITRE", "100", "2 B", "4401111", "3415550000"),
             ("L002", "SIN PISO", "SAN MARTIN", "50", "", "", "3415550001"),
             ("L003", "IGUALES", "", "", "", "4402222", "4402222"),
             ("L004", "VACIA", "", "", "", "", "")])
        self.db.execute("PRAGMA user_version = 10")
        self.db.commit()
        _reset()
        db = connection.get()
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], len(connection.MIGRACIONES))
        filas = {r[0]: tuple(r[1:]) for r in db.execute("SELECT codigo, direccion, telefono FROM sucursales")}
        self.assertEqual(filas, {"L001": ("MITRE 100, 2 B", "4401111 / 3415550000"),
                                 "L002": ("SAN MARTIN 50", "3415550001"),
                                 "L003": ("", "4402222"), "L004": ("", "")})
        cols = {r[1] for r in db.execute("PRAGMA table_info(sucursales)")}
        self.assertFalse(cols & {"entidad", "calle", "numero", "piso_depto", "celular"})
