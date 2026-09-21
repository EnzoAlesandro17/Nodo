"""Stock > Ingreso de equipos: el remito (pedido) de equipos que llegan, cargados de a uno por IMEI."""
import re
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

from db import imeis, ingresos, refs, stock
from models import EQUIPOS
from ui import remito_xlsx, theme
from ui.autocomplete import Combobox
from ui.base import Screen
from ui.form_dialog import FormDialog
from ui.formatting import fmt_date, parse_date
from ui.paths import escritorio

NOMBRE_INVALIDO = re.compile(r'[\\/:*?"<>|]')   # lo que Windows no admite en un nombre de archivo


class IngresoEquipos(Screen):
    title = "Stock · Ingreso de equipos"
    subtitle = "Pedido (remito) de equipos que llegan: se cargan los IMEI y el stock se suma solo"

    def __init__(self, parent):
        self.items = []   # [(imei, equipo_id, modelo)] en el orden del Treeview
        super().__init__(parent)

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=20)
        self._modelos()
        head = ttk.Frame(card, style="Inner.TFrame")
        head.pack(fill="x")
        options = refs.choices("sucursales")
        self.sucursales = {label: i for i, label in options}
        self.sucursal, self.pedido = tk.StringVar(), tk.StringVar()
        self.fecha = tk.StringVar(value=fmt_date(date.today().isoformat()))
        ttk.Label(head, text="Sucursal (destino)", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(head, text="Pedido / remito", style="Card.TLabel").grid(row=0, column=1, sticky="w", padx=(16, 0))
        ttk.Label(head, text="Fecha de ingreso", style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(16, 0))
        self.cmb_sucursal = Combobox(head, textvariable=self.sucursal, values=[label for _, label in options],
                                     state="readonly", width=22)
        self.cmb_sucursal.grid(row=1, column=0, sticky="w")
        ttk.Entry(head, textvariable=self.pedido, width=18).grid(row=1, column=1, padx=(16, 0))
        ttk.Entry(head, textvariable=self.fecha, width=12).grid(row=1, column=2, padx=(16, 0))
        self.sucursal.set(next((label for label in self.sucursales if label.startswith("3ROSARIO")), ""))

        add = ttk.Frame(card, style="Inner.TFrame")
        add.pack(fill="x", pady=(16, 8))
        ttk.Label(add, text="IMEI", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(add, text="Modelo (escribí para filtrar)", style="Card.TLabel").grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.imei, self.modelo = tk.StringVar(), tk.StringVar()
        self.entry = ttk.Entry(add, textvariable=self.imei, width=20)
        self.entry.grid(row=1, column=0, sticky="w")
        self.cmb = Combobox(add, textvariable=self.modelo, values=self.labels, width=42)
        self.cmb.grid(row=1, column=1, padx=(16, 0))
        ttk.Button(add, text="Agregar", style="Accent.TButton", command=self._agregar).grid(row=1, column=2, padx=(12, 0))
        ttk.Button(add, text="Modelo nuevo…", command=self._modelo_nuevo).grid(row=1, column=3, padx=(8, 0))
        self.error = ttk.Label(add, text="", foreground=theme.DANGER, style="Card.TLabel")
        self.error.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))
        self.entry.bind("<Return>", self._agregar)
        self.cmb.bind("<Return>", self._agregar)

        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=("n", "imei", "modelo"), show="headings", selectmode="browse")
        for col, text, width, stretch, anchor in (("n", "#", 50, False, "center"), ("imei", "IMEI", 170, False, "center"),
                                                  ("modelo", "Modelo", 400, True, "w")):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, minwidth=40, stretch=stretch, anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.bind("<Delete>", lambda e: self._quitar())
        self.entry.focus_set()

    def build_actions(self, bar):
        self.btn_registrar = ttk.Button(bar, text="Registrar ingreso", style="Accent.TButton", command=self._registrar)
        self.btn_registrar.pack(side="right")
        ttk.Button(bar, text="Exportar Excel", command=self._exportar).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="Limpiar", command=self._limpiar).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="Quitar seleccionado", command=self._quitar).pack(side="left")
        self.count = ttk.Label(bar, style="Sub.TLabel")
        self.count.pack(side="left", padx=16)
        self._refresh()

    # --- modelos -------------------------------------------------------
    def _modelos(self):
        options = refs.choices("equipos")
        self.modelos = {label: i for i, label in options}
        self.labels = [label for _, label in options]

    def _resolver_modelo(self):
        """El id del equipo escrito o elegido; si lo escrito coincide con uno solo, ese. None si no se puede."""
        text = self.modelo.get().strip()
        if text in self.modelos:
            return self.modelos[text]
        tokens = text.upper().split()
        found = [l for l in self.labels if tokens and all(t in l.upper() for t in tokens)]
        if len(found) == 1:
            self.modelo.set(found[0])
            return self.modelos[found[0]]
        return None

    def _modelo_nuevo(self):
        def guardar(data, dialog):
            if stock.equipos.get_by_codigo(data["codigo"]):
                return f"Ya existe un equipo con el código {data['codigo']}."
            stock.equipos.insert(data)
            self._modelos()
            self.cmb["values"] = self.labels
            self.modelo.set(next(l for l in self.labels if l.startswith(data["codigo"] + " - ")))
            self.entry.focus_set()

        FormDialog(self.winfo_toplevel(), "Nuevo modelo de equipo", EQUIPOS,
                   choices={"marca": stock.equipos.distinct("marca")}, on_save=guardar)

    # --- lista ---------------------------------------------------------
    def _fail(self, message):
        self.error.config(text=message)
        self.entry.focus_set()

    def _agregar(self, event=None):
        imei = re.sub(r"[\s\-]", "", self.imei.get())
        if not imei:
            return "break"
        if not (imei.isdigit() and len(imei) == 15):
            return self._fail("El IMEI tiene que tener 15 dígitos, solo números.")
        equipo_id = self._resolver_modelo()
        if equipo_id is None:
            self.error.config(text="Elegí el modelo de la lista.")
            self.cmb.focus_set()
            return "break"
        if any(i == imei for i, _, _ in self.items):
            return self._fail(f"El IMEI {imei} ya está en la lista.")
        reg = imeis.buscar(imei)
        if reg and reg["activo"]:
            return self._fail(f"El IMEI {imei} ya está cargado en {reg['codigo']} - {reg['descripcion']}.")
        self.items.append((imei, equipo_id, self.modelo.get().strip()))
        self.error.config(text="")
        self.imei.set("")   # el modelo queda: suelen ser varios seguidos del mismo
        self._refresh()
        self.entry.focus_set()
        return "break"

    def _quitar(self):
        sel = self.tree.selection()
        if sel:
            del self.items[self.tree.index(sel[0])]
            self._refresh()

    def _limpiar(self):
        if self.items and not messagebox.askyesno("Limpiar", "¿Vaciar la lista de equipos cargados?",
                                                  parent=self.winfo_toplevel()):
            return
        self.items.clear()
        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for n, (imei, _, modelo) in enumerate(self.items, start=1):
            self.tree.insert("", "end", values=(n, imei, modelo), tags=("odd",) if n % 2 == 0 else ())
        modelos = len({e for _, e, _ in self.items})
        self.count.config(text=f"{len(self.items)} equipos · {modelos} modelo{'' if modelos == 1 else 's'}")

    # --- guardar / exportar --------------------------------------------
    def _cabecera(self):
        """(sucursal_id, pedido, fecha ISO) o un mensaje de error."""
        self.cmb_sucursal.confirmar()
        if not self.sucursal.get():
            return "Elegí la sucursal de destino."
        pedido = self.pedido.get().strip()
        if not pedido:
            return "Falta el número de pedido / remito."
        try:
            fecha = parse_date(self.fecha.get())
        except ValueError:
            return "Fecha de ingreso: usá el formato dd/mm/aaaa."
        return self.sucursales[self.sucursal.get()], pedido, fecha

    def _registrar(self):
        top = self.winfo_toplevel()
        cab = self._cabecera()
        if isinstance(cab, str):
            return messagebox.showwarning("Ingreso de equipos", cab, parent=top)
        if not self.items:
            return messagebox.showwarning("Ingreso de equipos", "No hay equipos en la lista.", parent=top)
        sucursal_id, pedido, fecha = cab
        try:
            modelos = ingresos.registrar(pedido, sucursal_id, fecha, [(i, e) for i, e, _ in self.items])
        except ValueError as e:
            return messagebox.showerror("No se pudo registrar", str(e), parent=top)
        n = len(self.items)
        messagebox.showinfo("Ingreso registrado", f"Se cargaron {n} IMEI de {modelos} modelo{'' if modelos == 1 else 's'} "
                            f"y se sumó el stock en {self.sucursal.get().split(' - ')[0]}.", parent=top)
        if messagebox.askyesno("Exportar", "¿Querés guardar el pedido en Excel?", parent=top):
            self._exportar()
        self.items.clear()
        self.pedido.set("")
        self._refresh()

    def _exportar(self):
        top = self.winfo_toplevel()
        if not self.items:
            return messagebox.showwarning("Exportar", "No hay equipos en la lista.", parent=top)
        pedido = self.pedido.get().strip() or "sin numero"
        path = filedialog.asksaveasfilename(
            parent=top, title="Guardar pedido", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialdir=escritorio(), initialfile=f"PEDIDO {NOMBRE_INVALIDO.sub('_', pedido)}.xlsx")
        if not path:
            return
        destino = self.sucursal.get().split(" - ")[0]
        try:
            remito_xlsx.generar(path, destino, pedido, [(imei, modelo.split(" - ", 1)[-1]) for imei, _, modelo in self.items])
        except ImportError:
            return messagebox.showerror("Falta openpyxl", "Para guardar en Excel hace falta instalar openpyxl.", parent=top)
        except OSError as e:
            return messagebox.showerror("No se pudo guardar", str(e), parent=top)
        messagebox.showinfo("Exportar", f"Se guardó {Path(path).name}.", parent=top)
