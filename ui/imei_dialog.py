"""Ventana con los IMEI de un modelo de equipo: se cargan de a uno (escaneando o tipeando) y se quitan."""
import re
import tkinter as tk
from datetime import date
from tkinter import messagebox, ttk

from db import imeis, refs
from ui import theme
from ui.autocomplete import Combobox
from ui.base import arriba
from ui.formatting import fmt_date, parse_date

DIAS_PENALIZACION = 60   # a partir de acá la unidad se marca en rojo (regla de Claro: evitar penalizar a los 60 días)


class ImeiDialog(tk.Toplevel):
    def __init__(self, parent, equipo):
        super().__init__(parent, bg=theme.BG)
        self.equipo = equipo
        self.title(f"IMEI · {equipo['codigo']}")
        self.transient(parent)
        self.geometry("780x520")
        self.minsize(640, 420)
        self.rows = {}

        head = ttk.Frame(self, padding=(24, 18, 24, 6))
        head.pack(fill="x")
        ttk.Label(head, text="IMEI del modelo", style="Title.TLabel", font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(head, text=f"{equipo['codigo']} - {equipo['descripcion']}", style="Sub.TLabel").pack(anchor="w")

        form = ttk.Frame(self, padding=(24, 8, 24, 4))
        form.pack(fill="x")
        options = refs.choices("sucursales")
        self.sucursales = {label: i for i, label in options}
        ttk.Label(form, text="IMEI").grid(row=0, column=0, sticky="w")
        ttk.Label(form, text="Sucursal").grid(row=0, column=1, sticky="w", padx=(12, 0))
        ttk.Label(form, text="Ingreso").grid(row=0, column=2, sticky="w", padx=(12, 0))
        self.imei = tk.StringVar()
        self.sucursal = tk.StringVar()
        self.fecha = tk.StringVar(value=fmt_date(date.today().isoformat()))
        self.entry = ttk.Entry(form, textvariable=self.imei, width=20)
        self.entry.grid(row=1, column=0, sticky="w")
        self.cmb_sucursal = Combobox(form, textvariable=self.sucursal, values=[label for _, label in options],
                                     state="readonly", width=18)
        self.cmb_sucursal.grid(row=1, column=1, padx=(12, 0))
        fecha = ttk.Entry(form, textvariable=self.fecha, width=11)
        fecha.grid(row=1, column=2, padx=(12, 0))
        ttk.Button(form, text="Agregar", style="Accent.TButton", command=self._agregar).grid(row=1, column=3, padx=(12, 0))
        self.error = ttk.Label(form, text="", foreground=theme.DANGER)
        self.error.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.entry.bind("<Return>", self._agregar)
        fecha.bind("<Return>", self._agregar)

        wrap = ttk.Frame(self, padding=(24, 4, 24, 0))
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=("imei", "sucursal", "ingreso", "dias", "remito"), show="headings",
                                 selectmode="browse")
        for col, text, width in (("imei", "IMEI", 160), ("sucursal", "Sucursal", 120), ("ingreso", "Ingreso", 100),
                                 ("dias", "Antigüedad (días)", 120), ("remito", "Pedido", 100)):
            self.tree.heading(col, text=text, anchor="center")
            self.tree.column(col, width=width, minwidth=80, anchor="center", stretch=col == "sucursal")
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.tag_configure("viejo", foreground=theme.DANGER)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())

        bar = ttk.Frame(self, padding=(24, 10, 24, 6))
        bar.pack(fill="x")
        self.btn_quitar = ttk.Button(bar, text="Quitar", style="Danger.TButton", command=self._quitar)
        self.btn_quitar.pack(side="left")
        ttk.Button(bar, text="Cerrar", command=self.destroy).pack(side="right")
        self.resumen = ttk.Label(bar, style="Sub.TLabel")
        self.resumen.pack(side="right", padx=(0, 16))
        ttk.Label(self, text="Cargar un IMEI no cambia el stock: el stock se mueve en sus Movimientos. "
                             f"En rojo, los de {DIAS_PENALIZACION} días o más.", style="Sub.TLabel",
                  padding=(24, 0, 24, 14)).pack(anchor="w")

        default = imeis.de_equipo(equipo["id"])
        if default:   # la misma sucursal que el último cargado, para no elegirla cada vez
            self.sucursal.set(next((label for label, i in self.sucursales.items() if i == default[-1]["sucursal_id"]), ""))
        self._reload()
        self.bind("<Escape>", lambda e: self.destroy())
        arriba(self, parent)
        self.wait_visibility()
        self.grab_set()
        self.entry.focus_set()

    def _reload(self):
        rows = imeis.de_equipo(self.equipo["id"])
        self.rows = {r["id"]: r for r in rows}
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            tags = ("odd",) if i % 2 else ()
            if r["dias"] >= DIAS_PENALIZACION:
                tags += ("viejo",)
            self.tree.insert("", "end", iid=str(r["id"]), tags=tags,
                             values=(r["imei"], r["sucursal"] or "", fmt_date(r["fecha_ingreso"]), r["dias"], r["remito"]))
        self.resumen.config(text=f"{len(rows)} IMEI cargados · stock del modelo: {self.equipo['stock']}")
        self._update_buttons()

    def _update_buttons(self):
        self.btn_quitar.config(state="normal" if self.tree.selection() else "disabled")

    def _agregar(self, event=None):
        imei = re.sub(r"[\s\-]", "", self.imei.get())
        if not (imei.isdigit() and len(imei) == 15):
            return self._fail("El IMEI tiene que tener 15 dígitos, solo números.")
        self.cmb_sucursal.confirmar()
        if not self.sucursal.get():
            return self._fail("Elegí la sucursal donde está la unidad.")
        try:
            ingreso = parse_date(self.fecha.get())
        except ValueError:
            return self._fail("Ingreso: usá el formato dd/mm/aaaa.")
        try:
            imeis.agregar(self.equipo["id"], imei, self.sucursales[self.sucursal.get()], ingreso)
        except ValueError as e:
            return self._fail(str(e))
        self.error.config(text="")
        self.imei.set("")
        self._reload()
        self.entry.focus_set()

    def _fail(self, message):
        self.error.config(text=message)
        self.entry.focus_set()

    def _quitar(self):
        sel = self.tree.selection()
        if not sel:
            return
        row = self.rows[int(sel[0])]
        if messagebox.askyesno("Quitar IMEI", f"¿Querés quitar el IMEI {row['imei']}?\n\n"
                               "Es para una carga equivocada o una unidad que ya no está. No cambia el stock.",
                               icon="warning", parent=self):
            imeis.quitar(row["id"])
            self._reload()
