"""Consultas > Ventas y gestiones: buscar cualquier venta, gestión o gasto cargado, y anularlo."""
import tkinter as tk
from tkinter import messagebox, ttk

from db import operaciones
from ui import theme
from ui.autocomplete import Combobox, normalizar
from ui.base import Screen
from ui.formatting import fmt_datetime, fmt_money
from ui.period_filter import PeriodFilter

TODOS = "TODOS"
NOMBRES = {"ACCESORIOS": "Accesorios", "EQUIPOS": "Equipos", "CASIM": "CaSIM", "CATER": "CaTER", "REGULAR": "Regular",
           "PORTA": "Porta", "BAF": "BAF", "GASTO": "Gasto"}
TIPOS = [NOMBRES[t] for t in operaciones.TIPOS] + [NOMBRES[operaciones.TIPO_GASTO]]
POR_NOMBRE = {v: k for k, v in NOMBRES.items()}


class Consultas(Screen):
    title = "Consultas · Ventas y gestiones"
    subtitle = "Buscá cualquier venta, gestión o gasto cargado: por cliente, número, producto, vendedor o fecha"

    def __init__(self, parent):
        self.filas, self.visibles = [], {}
        super().__init__(parent)
        self.cargar()

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        top = ttk.Frame(card, style="Inner.TFrame")
        top.pack(fill="x", pady=(0, 12))
        self.buscar, self.tipo = tk.StringVar(), tk.StringVar(value=TODOS)
        ttk.Label(top, text="Buscar", style="Card.TLabel").pack(side="left")
        self.entry = ttk.Entry(top, textvariable=self.buscar, width=20)
        self.entry.pack(side="left", padx=(6, 18))
        self.buscar.trace_add("write", lambda *_: self._mostrar())
        ttk.Label(top, text="Tipo", style="Card.TLabel").pack(side="left")
        box = Combobox(top, textvariable=self.tipo, values=[TODOS] + TIPOS, state="readonly", width=12)
        box.pack(side="left", padx=(6, 18))
        box.bind("<<ComboboxSelected>>", lambda e: self._mostrar())
        self.periodo = PeriodFilter(top, self.cargar, modo_inicial="Mes")
        self.periodo.frame.pack(side="right")

        columnas = (("fecha", "Fecha y hora", 125, "center"), ("tipo", "Tipo", 90, "center"), ("cliente", "Cliente", 170, "w"),
                    ("detalle", "Detalle", 300, "w"), ("monto", "Monto", 110, "e"), ("vendedor", "Vendedor", 140, "w"),
                    ("sucursal", "Sucursal", 80, "center"))
        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in columnas], show="headings", selectmode="browse")
        for clave, texto, ancho, anchor in columnas:
            self.tree.heading(clave, text=texto, anchor=anchor)
            self.tree.column(clave, width=ancho, minwidth=50, stretch=clave == "detalle", anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.tag_configure("gasto", foreground=theme.DANGER)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._botones())
        self.tree.bind("<Double-1>", lambda e: self._detalle() if self.tree.identify_row(e.y) else None)
        self.tree.bind("<Delete>", lambda e: self._anular())

    def build_actions(self, bar):
        self.btn_detalle = ttk.Button(bar, text="Ver detalle", command=self._detalle)
        self.btn_anular = ttk.Button(bar, text="Anular", style="Danger.TButton", command=self._anular)
        self.btn_detalle.pack(side="left")
        self.btn_anular.pack(side="left", padx=8)
        self.total = ttk.Label(bar, style="Sub.TLabel")
        self.total.pack(side="right")
        self._botones()

    # --- datos ---------------------------------------------------------
    def cargar(self):
        desde, hasta = self.periodo.rango()
        self.filas = operaciones.operaciones(desde, hasta, con_gastos=True)
        for o in self.filas:   # Buscar encuentra cualquier dato de la fila, tal como se ve
            o["_texto"] = normalizar(" ".join((fmt_datetime(o["fecha"]), NOMBRES[o["tipo"]], o["cliente"], o["detalle"],
                                               self._monto(o), str(o["monto"]), o["vendedor"], o["sucursal"])))
        self._mostrar()

    def _mostrar(self):
        palabras = normalizar(self.buscar.get()).split()
        tipo = None if self.tipo.get() in ("", TODOS) else POR_NOMBRE[self.tipo.get()]
        seleccionada = self.tree.selection()
        filas = [o for o in self.filas if (tipo is None or o["tipo"] == tipo) and all(p in o["_texto"] for p in palabras)]
        self.visibles = {f"{o['origen']}:{o['id']}": o for o in filas}
        self.tree.delete(*self.tree.get_children())
        for n, o in enumerate(filas[:2000]):   # con miles de filas alcanza con las más recientes; se acota con la fecha
            tags = (("odd",) if n % 2 else ()) + (("gasto",) if o["tipo"] == operaciones.TIPO_GASTO else ())
            self.tree.insert("", "end", iid=f"{o['origen']}:{o['id']}", tags=tags, values=(
                fmt_datetime(o["fecha"]), NOMBRES[o["tipo"]], o["cliente"], o["detalle"], self._monto(o), o["vendedor"], o["sucursal"]))
        if seleccionada and seleccionada[0] in self.visibles:
            self.tree.selection_set(seleccionada[0])
        vendido = round(sum(o["monto"] for o in filas if o["tipo"] != operaciones.TIPO_GASTO), 2)
        gastos = round(sum(o["monto"] for o in filas if o["tipo"] == operaciones.TIPO_GASTO), 2)
        cortado = "  (se muestran las 2.000 más recientes)" if len(filas) > 2000 else ""
        self.total.config(text=f"{len(filas)} operaciones  ·  Vendido {fmt_money(vendido)}  ·  Gastos {fmt_money(gastos)}{cortado}",
                          foreground=theme.MUTED)
        self._botones()

    @staticmethod
    def _monto(o):
        """El monto para mostrar: los gastos en negativo, y vacío en las gestiones que no cobran (Regular, Porta, BAF)."""
        if o["tipo"] in ("REGULAR", "PORTA", "BAF"):
            return ""
        return fmt_money(-o["monto"] if o["tipo"] == operaciones.TIPO_GASTO else o["monto"])

    def _elegida(self):
        sel = self.tree.selection()
        return self.visibles.get(sel[0]) if sel else None

    def _botones(self):
        if hasattr(self, "btn_anular"):
            estado = "normal" if self.tree.selection() else "disabled"
            self.btn_detalle.config(state=estado)
            self.btn_anular.config(state=estado)

    # --- acciones ------------------------------------------------------
    def _detalle(self):
        o = self._elegida()
        if o:
            messagebox.showinfo("Detalle", "\n".join([
                f"{NOMBRES[o['tipo']]}  ·  {fmt_datetime(o['fecha'])}", "", f"Cliente / concepto:  {o['cliente'] or '—'}",
                f"Detalle:  {o['detalle'] or '—'}", f"Monto:  {fmt_money(o['monto'])}", f"Vendedor:  {o['vendedor'] or '—'}",
                f"Sucursal:  {o['sucursal'] or '—'}"]), parent=self.winfo_toplevel())

    def _anular(self):
        o = self._elegida()
        if not o:
            return
        extra = {"ventas": "Se anula la venta entera: sus productos vuelven al stock y sus pagos salen de la caja.",
                 "gastos": "Deja de contar en la caja."}.get(o["origen"], "Se devuelve el producto al stock." if o["origen"] not in ("baf",) else "")
        if not messagebox.askyesno("Anular", f"¿Querés anular esta operación?\n\n    {NOMBRES[o['tipo']]} · {o['cliente']} · {o['detalle']}\n"
                                   f"    {fmt_datetime(o['fecha'])} · {fmt_money(o['monto'])}\n\n{extra}".rstrip(),
                                   icon="warning", parent=self.winfo_toplevel()):
            return
        try:
            mensaje = operaciones.anular(o["origen"], o["id"])
        except Exception as e:   # no se puede dejar la pantalla sin explicar qué pasó
            return messagebox.showerror("No se pudo anular", str(e), parent=self.winfo_toplevel())
        messagebox.showinfo("Anulada", mensaje, parent=self.winfo_toplevel())
        self.cargar()
