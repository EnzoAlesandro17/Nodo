"""La Caja: cada operación entra una sola vez, con su monto y su cuenta, y las bajas y ediciones se reflejan."""
from db import caja, ventas
from db.gestiones import baf, casim, cater, gastos
from db.movimientos import mov_accesorios

from tests import BaseTemporal

DIA = "2026-09-15"


def por_tipo(rows):
    out = {}
    for r in rows:
        out.setdefault(r["tipo"], []).append(r)
    return out


class Caja(BaseTemporal):
    def setUp(self):
        super().setUp()
        self.sembrar()

    # --- helpers de carga ------------------------------------------------
    def venta(self, items, pagos, fecha=f"{DIA} 11:00:00"):
        cab = {"fecha": fecha, "cliente": "CONSUMIDOR FINAL", "vendedor_id": self.emp, "sucursal_id": self.suc,
               "cupon": "", "factura": ""}
        return ventas.registrar(cab, items, pagos)

    def casim(self, monto=500, fecha=f"{DIA} 12:00:00"):
        return casim.insert({"fecha": fecha, "nombre": "PEREZ, JUAN", "numero": "3415550000", "sim_id": self.sim,
                             "monto": monto, "cuenta_id": self.efe, "vendedor_id": self.emp, "sucursal_id": self.suc,
                             "observaciones": ""})

    def gasto(self, monto, fecha=f"{DIA} 18:00:00", cuenta=None):
        return gastos.insert({"fecha": fecha, "rubro": "VARIOS", "detalle": "LIMPIEZA", "factura": "", "monto": monto,
                              "cuenta_id": cuenta or self.efe, "vendedor_id": None, "sucursal_id": self.suc,
                              "observaciones": ""})

    def dia(self):
        return caja.movimientos(DIA, DIA)

    # --- ventas de accesorios -------------------------------------------
    def test_venta_con_pagos_combinados_e_intereses(self):
        self.venta([(self.funda, 2, 500), (self.cargador, 1, 500)], [(self.efe, 1000, 0), (self.visa, 500, 60)])
        t = por_tipo(self.dia())
        self.assertEqual(sorted((r["cuenta"], r["monto"]) for r in t["VENTA ACCESORIOS"]), [("EFE", 1000), ("VISA", 500)])
        self.assertEqual([(r["cuenta"], r["monto"]) for r in t["INTERESES"]], [("VISA", 60)])
        self.assertEqual(caja.totales(self.dia()), (1500, 60, 0, 1500))   # los intereses no son venta
        self.assertEqual((self.stock("accesorios", self.funda), self.stock("accesorios", self.cargador)), (8, 4))

    def test_venta_que_no_cierra_no_guarda_nada(self):
        with self.assertRaises(ValueError):
            self.venta([(self.funda, 2, 500)], [(self.efe, 900, 0)])
        self.assertEqual(self.dia(), [])
        self.assertEqual(self.stock("accesorios", self.funda), 10)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0], 0)

    def test_venta_con_producto_inexistente_se_revierte_entera(self):
        with self.assertRaises(Exception):
            self.venta([(self.funda, 1, 100), (99999, 1, 100)], [(self.efe, 200, 0)])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ventas").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM mov_accesorios").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM pagos").fetchone()[0], 0)
        self.assertEqual(self.stock("accesorios", self.funda), 10)

    def test_anular_venta_la_saca_de_la_caja_y_devuelve_stock(self):
        vid = self.venta([(self.funda, 2, 500), (self.cargador, 1, 500)], [(self.efe, 1000, 0), (self.visa, 500, 60)])
        mov = self.db.execute("SELECT id FROM mov_accesorios WHERE venta_id = ? LIMIT 1", (vid,)).fetchone()[0]
        mov_accesorios.deactivate(mov)
        self.assertEqual(self.dia(), [])
        self.assertEqual((self.stock("accesorios", self.funda), self.stock("accesorios", self.cargador)), (10, 5))

    def test_venta_suelta_de_stock_movimientos(self):
        mov_accesorios.insert({"fecha": f"{DIA} 10:00:00", "tipo": "VENTA", "producto_id": self.funda, "cantidad": 3,
                               "precio": 150.5, "cliente": "CONSUMIDOR FINAL", "medio": "VISA", "vendedor_id": self.emp,
                               "sucursal_id": self.suc, "cupon": "", "factura": "", "observaciones": ""})
        rows = self.dia()
        self.assertEqual([(r["tipo"], r["cuenta"], r["monto"]) for r in rows], [("VENTA ACCESORIOS", "VISA", 451.5)])

    def test_ingresos_y_conciliaciones_no_son_plata(self):
        for tipo, cant in (("INGRESO", 5), ("CONCILIACION", -2)):
            mov_accesorios.insert({"fecha": f"{DIA} 09:00:00", "tipo": tipo, "producto_id": self.funda, "cantidad": cant,
                                   "precio": 100, "cliente": "", "medio": "", "vendedor_id": self.emp,
                                   "sucursal_id": self.suc, "cupon": "", "factura": "", "observaciones": ""})
        self.assertEqual(self.dia(), [])
        self.assertEqual(self.stock("accesorios", self.funda), 13)

    # --- gestiones ------------------------------------------------------
    def test_casim_cuenta_una_sola_vez(self):
        self.casim(500)
        rows = self.dia()
        self.assertEqual([(r["tipo"], r["monto"], r["cuenta"]) for r in rows], [("CASIM", 500, "EFE")])   # no también VENTA EQUIPOS
        self.assertEqual(self.stock("equipos", self.sim), 99)

    def test_editar_casim_cambia_el_monto_sin_mover_de_mas_el_stock(self):
        cid = self.casim(500)
        data = {k: v for k, v in casim._get(cid).items() if k in casim.keys}
        casim.update(cid, {**data, "monto": 800})
        self.assertEqual([r["monto"] for r in self.dia()], [800])
        self.assertEqual(self.stock("equipos", self.sim), 99)
        casim.deactivate(cid)
        self.assertEqual(self.dia(), [])
        self.assertEqual(self.stock("equipos", self.sim), 100)

    def test_cater_una_fila_por_pago(self):
        cater.insert({"fecha": f"{DIA} 13:00:00", "nombre": "GOMEZ, ANA", "numero": "3415550001", "equipo_id": self.celu,
                      "imei": "", "monto": 300000, "pagos": [(self.efe, 100000), (self.fin, 200000)],
                      "vendedor_id": self.emp, "sucursal_id": self.suc, "observaciones": ""})
        t = por_tipo(self.dia())
        self.assertEqual(set(t), {"CATER"})
        self.assertEqual(sorted((r["cuenta"], r["monto"]) for r in t["CATER"]), [("EFE", 100000), ("FINANCIADO", 200000)])
        self.assertEqual(self.stock("equipos", self.celu), 2)

    def test_baf_aparece_con_monto_cero(self):
        baf.insert({"fecha": f"{DIA} 14:00:00", "vendedor_id": self.emp, "nombre": "LOPEZ", "documento": "",
                    "fecha_nacimiento": "", "email": "", "telefono": "3415550002", "telefono_alt": "", "localidad": "ROSARIO",
                    "calle": "MITRE", "altura": "100", "entre_calles": "", "torre_piso_depto": "", "tipo_domicilio": "Casa",
                    "plan_id": None, "cantidad_tv": "N/A", "fecha_pactada": "", "franja": "", "ot": "", "sds": "",
                    "fecha_instalacion": "", "estado": "Pactada", "con_form": 0, "observaciones": ""})
        rows = self.dia()
        self.assertEqual([(r["tipo"], r["monto"]) for r in rows], [("BAF", 0)])
        self.assertEqual(caja.totales(rows), (0, 0, 0, 0))

    # --- gastos ---------------------------------------------------------
    def test_gasto_resta_y_su_baja_lo_saca(self):
        self.casim(1000)
        gid = self.gasto(300)
        rows = self.dia()
        self.assertEqual(por_tipo(rows)["GASTO"][0]["monto"], -300)
        self.assertEqual(caja.totales(rows), (1000, 0, 300, 700))
        gastos.deactivate(gid)
        self.assertEqual(caja.totales(self.dia()), (1000, 0, 0, 1000))

    # --- fechas y redondeo ----------------------------------------------
    def test_el_rango_incluye_el_dia_entero_y_nada_mas(self):
        self.gasto(1, fecha="2026-09-14 23:59:59")
        self.gasto(2, fecha=f"{DIA} 00:00:00")
        self.gasto(4, fecha=f"{DIA} 23:59:59")
        self.gasto(8, fecha="2026-09-16 00:00:00")
        self.gasto(16, fecha=DIA)   # sin hora (como vinieron algunas cargas)
        self.assertEqual(caja.totales(self.dia())[2], 22)
        self.assertEqual(caja.totales(caja.movimientos())[2], 31)

    def test_centavos_sin_error_de_redondeo(self):
        for _ in range(10):
            self.gasto(0.1)
        self.venta([(self.funda, 3, 0.1)], [(self.efe, 0.3, 0)])
        self.assertEqual(caja.totales(self.dia()), (0.3, 0, 1.0, -0.7))


class CajaBaseReal(BaseTemporal):
    """Sobre una copia de data/nodo.db: la Caja coincide con lo que dicen las tablas por su cuenta."""
    copia_real = True

    def test_septiembre_cuadra_con_las_tablas(self):
        q = lambda sql: round(self.db.execute(sql).fetchone()[0] or 0, 2)
        rango = "fecha >= '2026-09-01' AND fecha < '2026-10-01'"
        gastos_tablas = q(f"SELECT SUM(monto) FROM gastos WHERE activo = 1 AND {rango}")
        casim_tablas = q(f"SELECT SUM(monto) FROM casim WHERE activo = 1 AND {rango}")
        rows = caja.movimientos("2026-09-01", "2026-09-30")
        t = por_tipo(rows)
        self.assertAlmostEqual(-sum(r["monto"] for r in t.get("GASTO", [])), gastos_tablas, places=2)
        self.assertAlmostEqual(sum(r["monto"] for r in t.get("CASIM", [])), casim_tablas, places=2)
        ventas_, intereses, gastos_, neto = caja.totales(rows)
        self.assertAlmostEqual(neto, ventas_ - gastos_, places=2)

    def test_filas_completas(self):
        for r in caja.movimientos():
            self.assertRegex(r["fecha"], r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}:\d{2})?$", r)
            self.assertIsInstance(r["monto"], float, r)
            self.assertTrue(r["tipo"], r)


class TestCobradoPorClaro(BaseTemporal):
    """Lo cobrado con una cuenta de Claro se ve en la Caja, pero no suma: esa plata va a Claro."""

    def test_se_ve_pero_no_suma(self):
        self.sembrar()   # FINANCIADO es de tipo CLARO
        cater.insert({"fecha": f"{DIA} 13:00:00", "nombre": "GOMEZ, ANA", "numero": "3415550001", "equipo_id": self.celu,
                      "imei": "", "monto": 300000, "pagos": [(self.efe, 100000), (self.fin, 200000)],
                      "vendedor_id": self.emp, "sucursal_id": self.suc, "observaciones": ""})
        cater.insert({"fecha": f"{DIA} 14:00:00", "nombre": "PEREZ", "numero": "3415550002", "equipo_id": self.celu,
                      "imei": "", "monto": 0, "pagos": [(self.fin, 0)],   # financiado sin monto: solo el registro
                      "vendedor_id": self.emp, "sucursal_id": self.suc, "observaciones": ""})
        rows = caja.movimientos(DIA, DIA)
        self.assertEqual(len(rows), 3)
        self.assertEqual(caja.totales(rows), (100000, 0, 0, 100000))
        self.assertEqual(caja.fuera_de_caja(rows), 200000)
