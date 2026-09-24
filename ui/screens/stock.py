"""Pantallas del menú Administrar > Stock. Cada una tiene un botón Movimientos que abre los de su tipo de producto."""
from tkinter import ttk

from db import stock as repos
from ui.imei_dialog import DIAS_PENALIZACION, ImeiDialog
from ui.screens import movimientos
from ui.stock_base import StockScreen


class StockAccesorios(StockScreen):
    title = "Stock · Accesorios"
    subtitle = "Inventario de accesorios"
    repo = repos.accesorios
    filter_all = "TODAS"
    movimientos = movimientos.MovAccesorios


class StockEquipos(StockScreen):
    title = "Stock · Equipos"
    subtitle = "Inventario de equipos"
    repo = repos.equipos
    filter_all = "TODAS"
    movimientos = movimientos.MovEquipos

    def extra_actions(self, bar):
        """Sin importar / exportar CSV (eso se hace desde Data); con los IMEI del modelo."""
        self.btn_imeis = ttk.Button(bar, text="IMEI", command=self.imeis)
        self.btn_imeis.pack(side="left", padx=(16, 0))
        super().extra_actions(bar)

    def row_tags(self, row):   # con una unidad de 60 días o más, la fila va en rojo
        return ("viejo",) if row.get("dias", 0) >= DIAS_PENALIZACION else ()

    def _display(self, field, row):
        if field.key in ("imeis", "dias") and not row.get("imeis"):
            return ""
        return super()._display(field, row)

    def _update_buttons(self):
        super()._update_buttons()
        if hasattr(self, "btn_imeis"):
            row_id = self._selected_id()
            es_chip = row_id is not None and self.rows[row_id]["marca"] == "SIM"   # los chips no llevan IMEI
            self.btn_imeis.config(state="disabled" if es_chip else self.btn_edit.cget("state"))

    def imeis(self):
        row_id = self._selected_id()
        if row_id is not None:
            ImeiDialog(self.winfo_toplevel(), self.rows[row_id])
