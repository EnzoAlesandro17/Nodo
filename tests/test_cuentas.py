"""Subcuentas: GETNET > GETNET VISA, GETNET QR...; CLARO > CLARO FINANCIADO, CLARO QR, CLARO TC-CTI."""
from db import administracion, connection, refs
from tests import BaseTemporal


class TestSubcuentas(BaseTemporal):
    def setUp(self):
        super().setUp()
        self.sembrar()   # EFE, VISA y FINANCIADO sueltas, como en una base anterior a las subcuentas
        with self.db:
            connection._m14_subcuentas(self.db)

    def padre_de(self, codigo):
        return administracion.cuentas.padre_por_codigo().get(codigo)

    def test_las_que_ya_estaban_se_renombran_sin_cambiar_de_id(self):
        self.assertEqual(self.padre_de("GETNET VISA"), "GETNET")
        self.assertEqual(self.padre_de("CLARO FINANCIADO"), "CLARO")
        self.assertEqual(self.db.execute("SELECT id FROM cuentas WHERE codigo = 'GETNET VISA'").fetchone()[0], self.visa)
        self.assertIsNone(self.db.execute("SELECT 1 FROM cuentas WHERE codigo IN ('VISA', 'FINANCIADO')").fetchone())
        self.assertIsNone(self.padre_de("EFE"))

    def test_el_medio_de_las_ventas_sueltas_se_renombra(self):
        with self.db:
            self.db.execute("INSERT INTO mov_accesorios (fecha, tipo, producto_id, cantidad, precio, medio, sucursal_id) "
                            "VALUES ('2026-09-01 00:00:00', 'VENTA', ?, 1, 100, 'NARANJA', ?)", (self.funda, self.suc))
            connection._m14_subcuentas(self.db)
        self.assertEqual(self.db.execute("SELECT medio FROM mov_accesorios").fetchone()[0], "GETNET NARANJA")

    def test_crea_las_que_faltan_y_repetir_no_duplica(self):
        with self.db:
            connection._m14_subcuentas(self.db)
        hijas = {c for c, p in administracion.cuentas.padre_por_codigo().items() if p == "GETNET"}
        self.assertEqual(hijas, {"GETNET QR", "GETNET QR DÉBITO", "GETNET VISA", "GETNET MASTER", "GETNET NARANJA",
                                 "GETNET AMEX"})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM cuentas WHERE codigo = 'CLARO TC-CTI'").fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT tipo FROM cuentas WHERE codigo = 'GETNET'").fetchone()[0], "TERMINAL")

    def test_para_cobrar_no_se_ofrecen_las_cuentas_padre(self):
        para_elegir = {c for _, c in refs.codigos("cuentas", para_elegir=True)}
        self.assertIn("GETNET VISA", para_elegir)
        self.assertIn("EFE", para_elegir)
        self.assertNotIn("GETNET", para_elegir)
        self.assertNotIn("CLARO", {label.split(" - ")[0] for _, label in refs.choices("cuentas")})
        self.assertIn("GETNET", {c for _, c in refs.codigos("cuentas")})   # las importaciones las ven todas

    def test_solo_dos_niveles(self):
        getnet = self.db.execute("SELECT id FROM cuentas WHERE codigo = 'GETNET'").fetchone()[0]
        repo = administracion.cuentas
        self.assertIsNone(repo.check_padre(None, getnet))
        self.assertIsNotNone(repo.check_padre(None, self.visa))      # GETNET VISA ya es subcuenta
        self.assertIsNotNone(repo.check_padre(getnet, self.efe))     # GETNET tiene subcuentas
        self.assertIsNotNone(repo.check_padre(self.efe, self.efe))   # de sí misma
