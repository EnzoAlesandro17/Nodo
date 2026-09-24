"""Caja: resumen de los movimientos de plata (ventas, CaSIM, CaTER, intereses y gastos)."""
from tkinter import ttk
import tkinter as tk

from db import caja
from ui import theme
from ui.autocomplete import Combobox, normalizar
from ui.base import Screen
from ui.formatting import fmt_datetime, fmt_money
from ui.period_filter import PeriodFilter

TODOS = "TODOS"


class Caja(Screen):
    title = "Caja"
    subtitle = "Lo cobrado y lo gastado, por período, tipo, cuenta, vendedor y sucursal"

    def __init__(self, parent):
        self.rows = []   # las filas del período (antes de filtrar por tipo, cuenta o sucursal)
        super().__init__(parent)
        self.refresh()

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        # renglón 1: Buscar y Tipo, con el período a la derecha; renglón 2: Cuenta y Sucursal
        top = ttk.Frame(card, style="Inner.TFrame")
        top.pack(fill="x", pady=(0, 8))
        filtros = ttk.Frame(card, style="Inner.TFrame")
        filtros.pack(fill="x", pady=(0, 12))
        self.buscar = tk.StringVar()
        ttk.Label(top, text="Buscar", style="Card.TLabel").pack(side="left")
        ttk.Entry(top, textvariable=self.buscar, width=20).pack(side="left", padx=(6, 18))
        self.buscar.trace_add("write", lambda *_: self._mostrar())
        self.tipo, self.cuenta, self.sucursal = (tk.StringVar(value=TODOS) for _ in range(3))
        self.boxes = {}
        for text, var, fila in (("Tipo", self.tipo, top), ("Cuenta", self.cuenta, filtros),
                                ("Sucursal", self.sucursal, filtros)):
            ttk.Label(fila, text=text, style="Card.TLabel").pack(side="left")
            box = Combobox(fila, textvariable=var, state="readonly", width=17)
            box.pack(side="left", padx=(6, 16))
            box.bind("<<ComboboxSelected>>", lambda e: self._mostrar())
            self.boxes[text] = box
        self.periodo = PeriodFilter(top, self.refresh, modo_inicial="Mes")
        self.periodo.frame.pack(side="right")

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
    def refresh(self):
        desde, hasta = self.periodo.rango()
        self.rows = caja.movimientos(desde, hasta)
        for r in self.rows:   # Buscar encuentra cualquier dato de la fila, tal como se ve
            r["_texto"] = normalizar(" ".join((fmt_datetime(r["fecha"]), r["tipo"], fmt_money(r["monto"]), str(r["monto"]),
                                               r["cuenta"], r["vendedor"], r["sucursal"], r["detalle"])))
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
        palabras = normalizar(self.buscar.get()).split()
        rows = [r for r in self.rows if all(v == TODOS or r[k] == v for k, v in filtros.items())
                and all(p in r["_texto"] for p in palabras)]
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
