"""Caja: resumen de los movimientos de plata (ventas, CaSIM, CaTER, intereses y gastos)."""
import tkinter as tk
from datetime import date
from tkinter import ttk

from db import caja
from ui import theme
from ui.autocomplete import Combobox
from ui.base import Screen
from ui.formatting import fmt_datetime, fmt_date, fmt_money, parse_date

TODOS = "TODOS"


class Caja(Screen):
    title = "Caja"
    subtitle = "Lo cobrado y lo gastado, por fecha, tipo, cuenta, vendedor y sucursal"

    def __init__(self, parent):
        self.rows = []   # las filas del período (antes de filtrar por tipo, cuenta o sucursal)
        super().__init__(parent)
        self.refresh()

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        top = ttk.Frame(card, style="Inner.TFrame")
        top.pack(fill="x", pady=(0, 12))
        hoy = date.today()
        self.desde = tk.StringVar(value=fmt_date(hoy.replace(day=1).isoformat()))
        self.hasta = tk.StringVar(value=fmt_date(hoy.isoformat()))
        self.tipo, self.cuenta, self.sucursal = (tk.StringVar(value=TODOS) for _ in range(3))

        ttk.Label(top, text="Desde", style="Card.TLabel").pack(side="left")
        for var in (self.desde, self.hasta):
            entry = ttk.Entry(top, textvariable=var, width=11)
            entry.pack(side="left", padx=(6, 0 if var is self.desde else 20))
            entry.bind("<Return>", lambda e: self.refresh())
            if var is self.desde:
                ttk.Label(top, text="Hasta", style="Card.TLabel").pack(side="left", padx=(12, 0))
        self.boxes = {}
        for text, var in (("Tipo", self.tipo), ("Cuenta", self.cuenta), ("Sucursal", self.sucursal)):
            ttk.Label(top, text=text, style="Card.TLabel").pack(side="left")
            box = Combobox(top, textvariable=var, state="readonly", width=17)
            box.pack(side="left", padx=(6, 16))
            box.bind("<<ComboboxSelected>>", lambda e: self._mostrar())
            self.boxes[text] = box
        ttk.Button(top, text="Hoy", command=lambda: self._periodo(hoy, hoy)).pack(side="left")
        ttk.Button(top, text="Este mes", command=lambda: self._periodo(hoy.replace(day=1), hoy)).pack(side="left", padx=6)
        ttk.Button(top, text="Todo", command=lambda: self._periodo(None, None)).pack(side="left")

        columns = (("fecha", "Fecha", 130, "center"), ("tipo", "Tipo de movimiento", 150, "w"),
                   ("monto", "Monto", 120, "e"), ("cuenta", "Cuenta", 110, "center"),
                   ("vendedor", "Vendedor", 160, "w"), ("sucursal", "Sucursal", 110, "center"),
                   ("detalle", "Detalle", 240, "w"))
        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for key, text, width, anchor in columns:
            self.tree.heading(key, text=text, anchor=anchor)
            self.tree.column(key, width=width, minwidth=60, stretch=key == "detalle", anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.tag_configure("gasto", foreground=theme.DANGER)
        self.tree.tag_configure("interes", foreground=theme.MUTED)

    def build_actions(self, bar):
        ttk.Button(bar, text="Actualizar", style="Accent.TButton", command=self.refresh).pack(side="left")
        self.totales = ttk.Label(bar, style="Sub.TLabel")
        self.totales.pack(side="right")

    # --- datos ---------------------------------------------------------
    def _periodo(self, desde, hasta):
        self.desde.set(fmt_date(desde.isoformat()) if desde else "")
        self.hasta.set(fmt_date(hasta.isoformat()) if hasta else "")
        self.refresh()

    def _fecha(self, var):
        """La fecha escrita como "AAAA-MM-DD", "" si está vacía, o None si no es una fecha válida."""
        texto = var.get().strip()
        if not texto:
            return ""
        try:
            return parse_date(texto)
        except ValueError:
            return None

    def refresh(self):
        desde, hasta = self._fecha(self.desde), self._fecha(self.hasta)
        if desde is None or hasta is None:
            self.totales.config(text="Fechas: usá el formato dd/mm/aaaa (o dejá vacío para no limitar).",
                                foreground=theme.DANGER)
            return
        self.rows = caja.movimientos(desde or None, hasta or None)
        for text, key in (("Tipo", "tipo"), ("Cuenta", "cuenta"), ("Sucursal", "sucursal")):
            values = [TODOS] + sorted({r[key] for r in self.rows if r[key]})
            self.boxes[text].configure(values=values)
            var = {"Tipo": self.tipo, "Cuenta": self.cuenta, "Sucursal": self.sucursal}[text]
            if var.get() not in values:
                var.set(TODOS)
        self._mostrar()

    def _mostrar(self):
        for var in (self.tipo, self.cuenta, self.sucursal):
            if not var.get():   # un filtro vaciado (se escribió algo que no es una opción) vuelve a TODOS
                var.set(TODOS)
        filtros = {"tipo": self.tipo.get(), "cuenta": self.cuenta.get(), "sucursal": self.sucursal.get()}
        rows = [r for r in self.rows if all(v == TODOS or r[k] == v for k, v in filtros.items())]
        self.tree.delete(*self.tree.get_children())
        for n, r in enumerate(rows):
            tags = (("odd",) if n % 2 else ()) + (("gasto",) if r["tipo"] == caja.TIPO_GASTO else
                                                  ("interes",) if r["tipo"] == caja.TIPO_INTERESES else ())
            self.tree.insert("", "end", tags=tags, values=(fmt_datetime(r["fecha"]), r["tipo"], fmt_money(r["monto"]),
                                                          r["cuenta"], r["vendedor"], r["sucursal"], r["detalle"]))
        ventas, intereses, gastos, neto = caja.totales(rows)
        self.totales.config(
            text=f"{len(rows)} movimientos  ·  Ventas {fmt_money(ventas)}  ·  Gastos {fmt_money(gastos)}  ·  "
                 f"Neto {fmt_money(neto)}  ·  Intereses (aparte) {fmt_money(intereses)}", foreground=theme.MUTED)
