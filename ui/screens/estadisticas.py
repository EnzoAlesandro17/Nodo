"""Consultas > Estadísticas: ventas por mes (por vendedor o por tipo) y los productos más vendidos."""
import tkinter as tk
from tkinter import ttk

from db import operaciones
from ui import theme
from ui.autocomplete import Combobox
from ui.base import Screen
from ui.formatting import fmt_int

MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
         "Diciembre")
MESES_CORTOS = tuple(m[:3] for m in MESES)
TODOS = "TODOS"
TOP = 25   # cuántos productos muestran los tops


def _combo(parent, texto, var, valores, comando, ancho=12):
    ttk.Label(parent, text=texto, style="Card.TLabel").pack(side="left", padx=(0, 6))
    box = Combobox(parent, textvariable=var, values=list(valores), state="readonly", width=ancho)
    box.pack(side="left", padx=(0, 18))
    box.bind("<<ComboboxSelected>>", lambda e: comando())
    return box


class Estadisticas(Screen):
    title = "Consultas · Estadísticas"
    subtitle = "Ventas por mes, por vendedor y por tipo; y los accesorios y equipos más vendidos"

    def build(self, card):
        card.configure(padding=16)
        años = [str(a) for a in operaciones.anios()]
        self.anio = tk.StringVar(value=años[0])
        notebook = ttk.Notebook(card)
        notebook.pack(fill="both", expand=True)
        self.tab_ventas = ttk.Frame(notebook, style="Inner.TFrame", padding=12)
        self.tab_acc = ttk.Frame(notebook, style="Inner.TFrame", padding=12)
        self.tab_eq = ttk.Frame(notebook, style="Inner.TFrame", padding=12)
        notebook.add(self.tab_ventas, text="  Ventas por mes  ")
        notebook.add(self.tab_acc, text="  Top accesorios  ")
        notebook.add(self.tab_eq, text="  Top equipos  ")

        # --- ventas por mes
        barra = ttk.Frame(self.tab_ventas, style="Inner.TFrame")
        barra.pack(fill="x", pady=(0, 10))
        self.agrupar, self.medida = tk.StringVar(value="Vendedor"), tk.StringVar(value="Monto")
        self.v_anio = _combo(barra, "Año", self.anio, años, self._todo, 8)
        _combo(barra, "Agrupar por", self.agrupar, ("Vendedor", "Tipo"), self._ventas, 12)
        _combo(barra, "Medida", self.medida, ("Monto", "Cantidad"), self._ventas, 10)
        columnas = ["grupo"] + [f"m{i}" for i in range(12)] + ["total"]
        self.pivot = self._tabla(self.tab_ventas, columnas, [("Grupo", 190, "w")] + [(m, 78, "e") for m in MESES_CORTOS]
                                 + [("Total", 100, "e")])
        self.pivot.tag_configure("total", background=theme.BORDER, font=theme.FONT_BOLD)
        self.nota = ttk.Label(self.tab_ventas, style="Muted.TLabel", wraplength=1000, justify="left")
        self.nota.pack(anchor="w", pady=(8, 0))

        # --- tops
        self.tops = {}
        for producto, tab in (("accesorios", self.tab_acc), ("equipos", self.tab_eq)):
            barra = ttk.Frame(tab, style="Inner.TFrame")
            barra.pack(fill="x", pady=(0, 10))
            mes, orden, sims = tk.StringVar(value=TODOS), tk.StringVar(value="Unidades"), tk.BooleanVar(value=False)
            _combo(barra, "Año", self.anio, años, self._todo, 8)
            _combo(barra, "Mes", mes, (TODOS,) + MESES, lambda p=producto: self._top(p), 13)
            _combo(barra, "Ordenar por", orden, ("Unidades", "Monto"), lambda p=producto: self._top(p), 10)
            if producto == "accesorios":
                ttk.Checkbutton(barra, text="Incluir SIMs", variable=sims, command=lambda: self._top("accesorios")).pack(side="left")
            tabla = self._tabla(tab, ["n", "codigo", "descripcion", "unidades", "monto", "barra"],
                                [("#", 40, "center"), ("Código", 130, "w"), ("Descripción", 380, "w"), ("Unidades", 90, "e"),
                                 ("Monto", 130, "e"), ("", 220, "w")])
            self.tops[producto] = (mes, orden, sims, tabla)
            if producto == "equipos":
                ttk.Label(tab, text="Se cuentan las ventas de equipos cargadas en Stock > Movimientos y en CaTER.",
                          style="Muted.TLabel").pack(anchor="w", pady=(8, 0))
        self._todo()

    def build_actions(self, bar):
        ttk.Label(bar, text="Se cuentan las ventas y gestiones vigentes (las dadas de baja y las BAF canceladas no).",
                  style="Sub.TLabel").pack(side="left")

    def _tabla(self, parent, claves, columnas):
        wrap = ttk.Frame(parent, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=claves, show="headings", selectmode="browse")
        for clave, (texto, ancho, anchor) in zip(claves, columnas):
            tree.heading(clave, text=texto, anchor=anchor)
            tree.column(clave, width=ancho, minwidth=40, stretch=clave in ("grupo", "descripcion"), anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.tag_configure("odd", background=theme.ZEBRA)
        return tree

    # --- datos ---------------------------------------------------------
    def _todo(self):
        self._ventas()
        self._top("accesorios")
        self._top("equipos")

    def _ventas(self):
        agrupar, medida = self.agrupar.get().lower(), self.medida.get().lower()
        filas, columnas, total = operaciones.por_mes(int(self.anio.get()), agrupar, medida)

        def texto(v):
            return "" if not v else fmt_int(round(v))

        self.pivot.delete(*self.pivot.get_children())
        for n, (grupo, meses, subtotal) in enumerate(filas):
            self.pivot.insert("", "end", tags=("odd",) if n % 2 else (), values=[grupo] + [texto(v) for v in meses] + [texto(subtotal)])
        self.pivot.insert("", "end", tags=("total",), values=["TOTAL"] + [texto(v) for v in columnas] + [texto(total)])
        self.nota.config(text=("Montos en pesos, sin los intereses de las cuotas. Regular, Porta y BAF no llevan monto: "
                               "para verlas usá «Cantidad». " if medida == "monto" else
                               "Cantidad de operaciones: cada venta de accesorios o equipos, cada CaSIM, CaTER, Regular, "
                               "Porta y BAF cuenta una. ") + f"Año {self.anio.get()}.")

    def _top(self, producto):
        mes_var, orden_var, sims_var, tabla = self.tops[producto]
        mes = None if mes_var.get() == TODOS else MESES.index(mes_var.get()) + 1
        filas = operaciones.top(producto, int(self.anio.get()), mes, con_sims=sims_var.get(), limite=2000)
        clave = "unidades" if orden_var.get() == "Unidades" else "monto"
        filas = sorted(filas, key=lambda f: (-f[clave], -f["unidades"], f["codigo"]))[:TOP]
        mayor = max((f[clave] for f in filas), default=0) or 1
        tabla.delete(*tabla.get_children())
        for n, f in enumerate(filas, start=1):
            tabla.insert("", "end", tags=("odd",) if n % 2 == 0 else (), values=(
                n, f["codigo"], f["descripcion"], fmt_int(f["unidades"]), f"$ {fmt_int(round(f['monto']))}",
                "█" * max(1, round(20 * f[clave] / mayor))))
        if not filas:
            tabla.insert("", "end", values=("", "", "No hay ventas en ese período.", "", "", ""))
