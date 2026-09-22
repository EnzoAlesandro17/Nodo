"""Consultas > Estadísticas: ventas de gestiones (por vendedor y por tipo) y los productos más vendidos."""
import tkinter as tk
from datetime import date
from tkinter import ttk

from db import caja, operaciones
from ui import theme
from ui.autocomplete import Combobox
from ui.base import Screen
from ui.formatting import fmt_int
from ui.period_filter import MESES, PeriodFilter

TOP = 25   # cuántos productos muestran los tops


class Estadisticas(Screen):
    title = "Consultas · Estadísticas"
    subtitle = "Ventas de gestiones por vendedor y por tipo, con proyección del mes; y los accesorios y equipos más vendidos"

    def build(self, card):
        card.configure(padding=16)
        años = [str(a) for a in operaciones.anios()]
        notebook = ttk.Notebook(card)
        notebook.pack(fill="both", expand=True)
        self.tab_gestiones = ttk.Frame(notebook, style="Inner.TFrame", padding=12)
        self.tab_acc = ttk.Frame(notebook, style="Inner.TFrame", padding=12)
        self.tab_eq = ttk.Frame(notebook, style="Inner.TFrame", padding=12)
        notebook.add(self.tab_gestiones, text="  Gestiones  ")
        notebook.add(self.tab_acc, text="  Top accesorios  ")
        notebook.add(self.tab_eq, text="  Top equipos  ")

        self._build_gestiones(self.tab_gestiones, años)

        self.tops = {}
        for producto, tab in (("accesorios", self.tab_acc), ("equipos", self.tab_eq)):
            self._build_top(tab, producto, años)
        self._top_todo()

    def build_actions(self, bar):
        ttk.Label(bar, text="Se cuentan las ventas y gestiones vigentes (las dadas de baja y las BAF canceladas no).",
                  style="Sub.TLabel").pack(side="left")

    def _tabla(self, parent, claves, columnas):
        wrap = ttk.Frame(parent, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=claves, show="headings", selectmode="browse")
        for clave, (texto, ancho, anchor) in zip(claves, columnas):
            tree.heading(clave, text=texto, anchor=anchor)
            tree.column(clave, width=ancho, minwidth=40, stretch=clave in ("descripcion", "nombre", "vendedor"), anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.tag_configure("odd", background=theme.ZEBRA)
        return tree

    # --- gestiones ---------------------------------------------------------
    def _build_gestiones(self, tab, años):
        self.proyeccion = ttk.Label(tab, style="Card.TLabel", font=theme.FONT_BOLD, wraplength=1000, justify="left")
        self.proyeccion.pack(anchor="w", pady=(0, 12))
        self._proyeccion()

        self.periodo_gestiones = PeriodFilter(tab, self._gestiones, años, modo_inicial="Mes")
        self.periodo_gestiones.frame.pack(fill="x", pady=(0, 6))

        self.g_total = ttk.Label(tab, style="Card.TLabel", font=theme.FONT_BOLD)
        self.g_total.pack(anchor="w", pady=(10, 12))

        self.g_wrap = ttk.Frame(tab, style="Inner.TFrame")
        self.g_wrap.pack(fill="both", expand=True)

        self.g_nota = ttk.Label(tab, style="Muted.TLabel", wraplength=1000, justify="left")
        self.g_nota.pack(anchor="w", pady=(10, 0))
        self._gestiones()

    def _proyeccion(self):
        p = caja.proyeccion_mes_actual()
        cerrados = f"{p['dias_cerrados']} cerrado{'' if p['dias_cerrados'] == 1 else 's'}" if p["dias_cerrados"] else \
            "ninguno cerrado"
        self.proyeccion.config(
            text=f"Proyección de {MESES[p['mes'] - 1].lower()}: si se mantiene el ritmo, el mes cerraría en "
                 f"$ {fmt_int(round(p['proyectado']))} (vendido hasta hoy, día {p['dia']} de {p['dias_mes']} "
                 f"({cerrados}): $ {fmt_int(round(p['ventas']))}). Los días cerrados se cargan en "
                 f"Administración > Días cerrados.")

    def _mes_actual_elegido(self):
        """True si el período elegido es, justo, el mes en curso (ahí tiene sentido proyectar)."""
        p = self.periodo_gestiones
        hoy = date.today()
        return (p.modo.get() == "Mes" and int(p.anio.get()) == hoy.year
                and MESES.index(p.mes.get()) + 1 == hoy.month)

    def _gestiones(self):
        desde, hasta = self.periodo_gestiones.rango()
        tipos, filas, columnas, total_monto, total_cant = operaciones.resumen_gestiones(desde, hasta)
        proyectar = self._mes_actual_elegido()

        for w in self.g_wrap.winfo_children():
            w.destroy()
        claves = ["vendedor"] + tipos + ["total"] + (["proyeccion"] if proyectar else [])
        cols_ui = ([("Vendedor", 200, "w")] + [(t, 90, "center") for t in tipos] + [("Total", 90, "center")]
                  + ([("Proyección", 100, "center")] if proyectar else []))
        tree = self._tabla(self.g_wrap, claves, cols_ui)
        tree.tag_configure("total", background=theme.BORDER, font=theme.FONT_BOLD)
        tree.tag_configure("proyeccion", background=theme.ZEBRA, font=theme.FONT_BOLD)

        factor = caja.factor_proyeccion() if proyectar else 1
        for n, (vendedor, valores, total_fila) in enumerate(filas):
            extra = [round(total_fila * factor)] if proyectar else []
            tree.insert("", "end", tags=("odd",) if n % 2 else (),
                       values=[vendedor] + [v or "" for v in valores] + [total_fila] + extra)
        if filas:
            extra = [round(total_cant * factor)] if proyectar else []
            tree.insert("", "end", tags=("total",), values=["TOTAL"] + [v or "" for v in columnas] + [total_cant] + extra)
            if proyectar:
                fila_proy = [round(c * factor) for c in columnas]
                tree.insert("", "end", tags=("proyeccion",),
                           values=["Proyección"] + fila_proy + [round(total_cant * factor)] * 2)
        else:
            tree.insert("", "end", values=["Sin gestiones en el período."] + [""] * (len(tipos) + 1 + proyectar))

        self.g_total.config(text=f"Ventas totales {self.periodo_gestiones.texto()}: $ {fmt_int(round(total_monto))}"
                                 f"  ·  {total_cant} {'gestión' if total_cant == 1 else 'gestiones'}")
        nota = ("Cantidad de gestiones por vendedor y por tipo (CaTER, Regular, Porta y BAF; CaSIM no entra "
               "acá). Regular, Porta y BAF no cobran: el monto de arriba es solo de CaTER. Solo gestiones "
               "vigentes (las dadas de baja y las BAF canceladas no cuentan). Por ahora no incluye accesorios "
               "ni equipos.")
        if proyectar:
            nota += " La columna y la fila «Proyección» estiman cómo cerraría el mes si sigue este ritmo."
        self.g_nota.config(text=nota)

    # --- tops ----------------------------------------------------------
    def _build_top(self, tab, producto, años):
        barra = ttk.Frame(tab, style="Inner.TFrame")
        barra.pack(fill="x", pady=(0, 10))
        periodo = PeriodFilter(barra, lambda p=producto: self._top(p), años)
        periodo.frame.pack(side="left")
        orden, sims = tk.StringVar(value="Unidades"), tk.BooleanVar(value=False)
        ttk.Label(barra, text="Ordenar por", style="Card.TLabel").pack(side="left", padx=(18, 6))
        box = Combobox(barra, textvariable=orden, values=("Unidades", "Monto"), state="readonly", width=10)
        box.pack(side="left", padx=(0, 18))
        box.bind("<<ComboboxSelected>>", lambda e, p=producto: self._top(p))
        ttk.Checkbutton(barra, text="Incluir SIMs", variable=sims, command=lambda p=producto: self._top(p)).pack(side="left")
        tabla = self._tabla(tab, ["n", "codigo", "descripcion", "unidades", "monto", "barra"],
                            [("#", 40, "center"), ("Código", 130, "w"), ("Descripción", 380, "w"), ("Unidades", 90, "e"),
                             ("Monto", 130, "e"), ("", 220, "w")])
        self.tops[producto] = (periodo, orden, sims, tabla)
        if producto == "equipos":
            ttk.Label(tab, text="Se cuentan las ventas de equipos cargadas en Stock > Movimientos y en CaTER "
                                "(los chips que entrega CaSIM, Regular y Porta quedan afuera salvo «Incluir SIMs»).",
                      style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def _top_todo(self):
        self._top("accesorios")
        self._top("equipos")

    def _top(self, producto):
        periodo, orden_var, sims_var, tabla = self.tops[producto]
        desde, hasta = periodo.rango()
        filas = operaciones.top(producto, desde, hasta, con_sims=sims_var.get(), limite=2000)
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
