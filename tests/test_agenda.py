"""Inicio: agenda de instalaciones de BAF y portaciones, y novedades del día."""
from datetime import date

from db import agenda

from tests import BaseTemporal

HOY = date(2026, 9, 24)


class Agenda(BaseTemporal):
    def setUp(self):
        super().setUp()
        self.sembrar()
        db = self.db
        with db:
            plan = db.execute("SELECT id FROM planes WHERE codigo = '200MB'").fetchone()[0]
            linea = db.execute("INSERT INTO planes (codigo, categoria, descripcion) VALUES ('2GB', 'LÍNEAS', 'X')").lastrowid
            for nombre, estado, pactada, instalacion in (
                    ("PACTADA", "Pactada", "2026-09-26", ""),
                    ("REPROGRAMADA", "Pactada", "2026-09-04", "2026-09-30"),   # se reprogramó: vale la de instalación
                    ("ATRASADA", "Falta pactar", "2026-09-20", ""),
                    ("INSTALADA", "Instalada", "2026-09-25", "2026-09-25"),
                    ("CANCELADA", "Cancelada", "2026-09-25", ""),
                    ("LEJOS", "Pactada", "2026-10-30", "")):
                db.execute("INSERT INTO baf (vendedor_id, nombre, telefono, localidad, calle, altura, tipo_domicilio, "
                           "plan_id, estado, fecha_pactada, fecha_instalacion) VALUES (?, ?, '3410000000', 'ROSARIO', "
                           "'MITRE', '1', 'Casa', ?, ?, ?, ?)", (self.emp, nombre, plan, estado, pactada, instalacion))
            for nombre, portacion in (("HOY", "2026-09-24"), ("PASADA", "2026-09-01"), ("SIN FECHA", "")):
                db.execute("INSERT INTO porta (nombre, numero_portar, plan_id, nim, id_gestion, vendedor_id, fecha_portacion) "
                           "VALUES (?, '3410000001', ?, '', '', ?, ?)", (nombre, linea, self.emp, portacion))

    def test_agenda(self):
        filas = [(f["tipo"], f["cliente"], f["fecha"], f["atrasada"]) for f in agenda.agenda(HOY, 14)]
        self.assertEqual(filas, [("BAF", "ATRASADA", "2026-09-20", True), ("PORTA", "HOY", "2026-09-24", False),
                                 ("BAF", "PACTADA", "2026-09-26", False), ("BAF", "REPROGRAMADA", "2026-09-30", False)])

    def test_novedades(self):
        """Lo cargado hoy (las filas de arriba se cargan con la fecha de hoy); las BAF canceladas no cuentan."""
        self.assertEqual(agenda.novedades(date.today()), {"operaciones": {"PORTA": 3, "BAF": 5}, "arqueos": 0})
        self.assertEqual(agenda.novedades(date(2000, 1, 1)), {"operaciones": {}, "arqueos": 0})
