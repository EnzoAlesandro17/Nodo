"""Pantalla genérica de stock: productos con alta / edición / baja (CodigoScreen)."""
from tkinter import ttk

from ui.codigo_base import CodigoScreen


class StockScreen(CodigoScreen):
    """Stock de productos. La carga masiva por CSV está en la sección Data."""
    noun, noun_plural = "producto", "productos"
    form_new, form_edit = "Nuevo producto", "Editar producto"
    movimientos = None   # pantalla de movimientos de este tipo de producto (botón Movimientos)

    def extra_actions(self, bar):
        ttk.Button(bar, text="Movimientos", command=lambda: self.winfo_toplevel().show(self.movimientos)
                   ).pack(side="left", padx=(16, 0))

    def _display(self, field, row):
        if field.key == "stock" and row.get("virtual"):
            return "—"   # producto virtual: no maneja stock
        return super()._display(field, row)
