"""Cargas masivas: importar miles de registros por CSV, todo o nada, y la Caja sigue rápida con un volumen grande."""
import csv
import random
import time

from db import caja, importer, stock
from db.gestiones import gastos

from tests import BaseTemporal

N_CSV = 5000        # accesorios en un CSV
N_AÑOS = 3          # años de operaciones simuladas para medir la Caja
POR_DIA = 40        # operaciones por día (la caja de 3ROSARIO anda por 20-50)


class ImportarCsv(BaseTemporal):
    def csv(self, nombre, filas):
        path = self.path.with_name(nombre)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["Código", "Categoría", "Descripción", "Precio mayorista", "Precio minorista"])
            w.writerows(filas)
        return path

    def filas(self, n, precio=1000):
        return [[f"A{i:05d}", "FUNDAS", f"FUNDA MODELO {i}", f"{precio},50", f"{precio * 2},25"] for i in range(n)]

    def test_miles_de_altas_y_reimportar_no_cambia_nada(self):
        t0 = time.perf_counter()
        plan = importer.build_plan(stock.accesorios, self.csv("alta.csv", self.filas(N_CSV)))
        self.assertEqual((len(plan.inserts), len(plan.skipped)), (N_CSV, 0))
        importer.apply_plan(stock.accesorios, plan)
        segundos = time.perf_counter() - t0
        self.assertEqual(self.db.execute("SELECT COUNT(*), TOTAL(precio_minorista) FROM accesorios").fetchone()[:],
                         (N_CSV, round(N_CSV * 2000.25, 2)))
        self.assertLess(segundos, 30, f"importar {N_CSV} tardó {segundos:.1f} s")

        otra = importer.build_plan(stock.accesorios, self.csv("alta.csv", self.filas(N_CSV)))
        self.assertEqual((len(otra.inserts), len(otra.updates), otra.unchanged), (0, 0, N_CSV))

    def test_exportar_e_importar_es_identico(self):
        importer.apply_plan(stock.accesorios, importer.build_plan(stock.accesorios, self.csv("a.csv", self.filas(500))))
        salida = self.path.with_name("export.csv")
        importer.export_csv(stock.accesorios, salida)
        plan = importer.build_plan(stock.accesorios, salida)
        self.assertEqual((len(plan.inserts), len(plan.updates), len(plan.conflicts), plan.unchanged), (0, 0, 0, 500))

    def test_cambio_masivo_de_precios(self):
        importer.apply_plan(stock.accesorios, importer.build_plan(stock.accesorios, self.csv("a.csv", self.filas(N_CSV))))
        plan = importer.build_plan(stock.accesorios, self.csv("b.csv", self.filas(N_CSV, precio=1500)))
        self.assertEqual(len(plan.updates), N_CSV)
        importer.apply_plan(stock.accesorios, plan)
        self.assertEqual(self.db.execute("SELECT MIN(precio_mayorista), MAX(precio_mayorista) FROM accesorios").fetchone()[:],
                         (1500.5, 1500.5))

    def test_filas_malas_se_saltean_sin_frenar_las_buenas(self):
        filas = self.filas(100) + [["", "X", "SIN CODIGO", "1", "1"], ["B1", "X", "PRECIO MALO", "abc", "1"],
                                   ["A00001", "X", "REPETIDO", "1", "1"]]
        plan = importer.build_plan(stock.accesorios, self.csv("m.csv", filas))
        self.assertEqual((len(plan.inserts), len(plan.skipped)), (100, 3))

    def test_si_falla_a_mitad_no_queda_nada(self):
        plan = importer.build_plan(stock.accesorios, self.csv("a.csv", self.filas(1000)))
        plan.inserts[700]["data"]["descripcion"] = None   # NOT NULL: revienta en la fila 701
        with self.assertRaises(Exception):
            importer.apply_plan(stock.accesorios, plan)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM accesorios").fetchone()[0], 0)


class VolumenCaja(BaseTemporal):
    """Años de operaciones: la Caja tiene que seguir sumando bien y rápido."""

    def test_caja_con_años_de_datos(self):
        self.sembrar()
        rnd = random.Random(1)
        filas, total = [], 0.0
        for d in range(365 * N_AÑOS):
            y, rest = 2024 + d // 365, d % 365
            fecha = f"{y}-{rest // 31 % 12 + 1:02d}-{rest % 28 + 1:02d}"
            for i in range(POR_DIA):
                monto = round(rnd.uniform(100, 50000), 2)
                total += monto
                filas.append((f"{fecha} {8 + i % 12:02d}:{i:02d}:00", "VARIOS", "GASTO", "", monto, self.efe,
                              self.emp, self.suc, ""))
        with self.db:   # carga directa (como una importación): un gasto por fila
            self.db.executemany("INSERT INTO gastos (fecha, rubro, detalle, factura, monto, cuenta_id, vendedor_id, "
                                "sucursal_id, observaciones) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", filas)

        t0 = time.perf_counter()
        rows = caja.movimientos()
        todo = time.perf_counter() - t0
        self.assertEqual(len(rows), len(filas))
        self.assertAlmostEqual(caja.totales(rows)[2], round(total, 2), places=2)
        self.assertLess(todo, 10, f"la Caja completa ({len(filas)} filas) tardó {todo:.1f} s")

        t0 = time.perf_counter()
        mes = caja.movimientos("2025-03-01", "2025-03-31")
        un_mes = time.perf_counter() - t0
        self.assertTrue(mes)
        self.assertLess(un_mes, 2, f"un mes tardó {un_mes:.2f} s sobre {len(filas)} filas")

        t0 = time.perf_counter()
        gastos.list()
        self.assertLess(time.perf_counter() - t0, 10)
        self.assertEqual(self.db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
