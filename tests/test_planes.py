"""Planes unificados: una sola tabla con categoría (LÍNEAS para Regular y Porta, BAF para fibra)."""
import csv

from db import administracion, connection, importer, refs

from tests import BaseTemporal, _reset


class Planes(BaseTemporal):
    def test_base_nueva_trae_los_de_fibra_como_baf(self):
        self.assertEqual([c for _, c in refs.choices("planes", "BAF")],
                         ["200MB - FIBRA 200 MB", "500MB - FIBRA 500 MB", "800MB - FIBRA 800 MB"])
        self.assertEqual(refs.choices("planes", "LÍNEAS"), [])

    def test_csv_acepta_la_categoria_sin_acento_y_rechaza_otras(self):
        path = self.path.with_name("p.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Nombre clave", "Categoría", "Descripción"])
            w.writerows([["4GB", "lineas", "PLAN 4 GB"], ["X", "OTRA", "MALA"]])
        plan = importer.build_plan(administracion.planes, path)
        self.assertEqual([i["data"]["categoria"] for i in plan.inserts], ["LÍNEAS"])
        self.assertEqual([clave for _, clave, _ in plan.skipped], ["X"])


class Migracion12(BaseTemporal):
    def test_planes_baf_pasan_a_planes_y_baf_apunta_ahi(self):
        """Simula una base en versión 11: planes sin categoría, planes_baf aparte y BAF apuntando a planes_baf."""
        db = self.db
        with db:
            db.execute("DELETE FROM planes")
            db.execute("ALTER TABLE planes DROP COLUMN categoria")
            db.execute("INSERT INTO planes (codigo, descripcion) VALUES ('4GB', 'PLAN 4 GB')")
            db.execute(connection.PLANES_BAF_VIEJA_DDL)
            fibra = db.execute("INSERT INTO planes_baf (codigo, descripcion) VALUES ('500MB', 'FIBRA 500 MB')").lastrowid
            db.execute("INSERT INTO planes_baf (codigo, descripcion) VALUES ('4GB', 'MISMO CODIGO')")
            db.execute("DROP TABLE baf")
            db.execute(connection.BAF_DDL.replace("REFERENCES planes(id)", "REFERENCES planes_baf(id)"))
            emp = db.execute("INSERT INTO empleados (nombre) VALUES ('AMADORI, ENZO')").lastrowid
            db.execute("INSERT INTO baf (vendedor_id, nombre, telefono, localidad, calle, altura, tipo_domicilio, plan_id) "
                       "VALUES (?, 'PEREZ', '3415550000', 'ROSARIO', 'MITRE', '100', 'Casa', ?)", (emp, fibra))
            db.execute("PRAGMA user_version = 11")
        _reset()
        db = connection.get()
        self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], len(connection.MIGRACIONES))
        planes = {r[0]: tuple(r[1:]) for r in db.execute("SELECT codigo, categoria, descripcion FROM planes")}
        self.assertEqual(planes, {"4GB": ("LÍNEAS", "PLAN 4 GB"), "500MB": ("BAF", "FIBRA 500 MB"),
                                  "4GB-BAF": ("BAF", "MISMO CODIGO")})
        self.assertEqual(db.execute("SELECT p.codigo FROM baf g JOIN planes p ON p.id = g.plan_id").fetchone()[0], "500MB")
        self.assertIsNone(db.execute("SELECT 1 FROM sqlite_master WHERE name = 'planes_baf'").fetchone())
        self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])


class MailDeBaf(BaseTemporal):
    def test_el_mail_de_baf_es_un_campo_mail(self):
        """El mail de BAF no se pasa a mayúsculas al editar (era un texto común y el formulario lo ponía en mayúsculas)."""
        import models
        self.assertEqual(next(f.kind for f in models.BAF if f.key == "email"), "email")
