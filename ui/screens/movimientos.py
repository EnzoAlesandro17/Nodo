"""Movimientos de stock (botón Movimientos de Administrar > Stock > Accesorios / Equipos): ingresos, ventas y
conciliaciones."""
from tkinter import ttk

from db import movimientos as repos
from ui.gestion_base import GestionScreen


class MovimientoScreen(GestionScreen):
    noun, noun_plural = "movimiento", "movimientos"
    left_keys = ("producto_id", "cliente")
    form_new, form_edit = "Nuevo movimiento", "Editar movimiento"
    stock = ""   # nombre de la pantalla de stock a la que vuelve (en ui.screens.stock)

    def extra_actions(self, bar):
        ttk.Button(bar, text="Volver al stock", command=self._volver).pack(side="left", padx=(16, 0))

    def _volver(self):
        from ui.screens import stock   # acá: stock importa este módulo
        self.winfo_toplevel().show(getattr(stock, self.stock))

    def _defaults(self):
        """Sucursal y vendedor del último movimiento, para no elegirlos cada vez."""
        last = self.repo.list()[:1]
        return {k: last[0][k] for k in ("sucursal_id", "vendedor_id")} if last else {}

    # --- guardado ------------------------------------------------------
    def _check(self, data, row_id=None):
        cantidad = data["cantidad"]
        if cantidad == 0:
            return "La cantidad no puede ser 0."
        if data["tipo"] != "CONCILIACION" and cantidad < 0:
            return "La cantidad tiene que ser positiva. Para restar stock por un conteo usá una conciliación."
        if data["tipo"] == "VENTA" and not data["medio"]:
            return "Elegí el medio de cobro de la venta."
        return self.repo.check_imei(data, row_id)

    def _save_new(self, data, dialog):
        error = self._check(data) or self._confirm_stock(data)
        if error:
            return error
        self.reload(select=self.repo.insert(data))

    def _save_edit(self, row_id, data):
        if self.rows[row_id].get("venta_id"):
            return ("Este producto es parte de una venta cargada en Nuevo > Accesorios: para corregirla, dala de baja "
                    "(se anula la venta entera) y cargala de nuevo.")
        error = self._check(data, row_id) or self._confirm_stock(data, self.rows[row_id])
        if error:
            return error
        self.repo.update(row_id, data)
        self.reload(select=row_id)

    def delete_prompt(self, row):
        if row.get("venta_id"):
            return ("Anular venta",
                    f"Este producto es parte de la venta {row['venta_id']} (Nuevo > Accesorios):\n\n    {row['cantidad']} × "
                    f"{row['producto_id_label']}\n\nSe anula la venta entera: todos sus productos vuelven al stock y sus "
                    "pagos salen de la caja. ¿Seguís?")
        return ("Dar de baja",
                f"¿Querés dar de baja este movimiento?\n\n    {row['tipo']} · {row['cantidad']} × "
                f"{row['producto_id_label']}\n\nSe revierte su efecto en el stock.")


class MovAccesorios(MovimientoScreen):
    title = "Stock · Movimientos de accesorios"
    subtitle = "Ingresos, ventas y conciliaciones de accesorios"
    repo = repos.mov_accesorios
    stock = "StockAccesorios"


class MovEquipos(MovimientoScreen):
    title = "Stock · Movimientos de equipos"
    subtitle = "Ingresos, ventas y conciliaciones de equipos"
    repo = repos.mov_equipos
    stock = "StockEquipos"
