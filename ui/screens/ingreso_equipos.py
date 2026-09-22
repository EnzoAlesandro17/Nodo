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
    subtitle = ("Pedido (remito) de equipos y chips que llegan: los equipos se cargan por IMEI, los chips por "
               "cantidad (Claro no manda un número de serie que valga la pena cargar); el stock se suma solo")

    def __init__(self, parent):
        self.items = []   # [(imei, equipo_id, modelo)] en el orden del Treeview
        self.chips = []   # [(accesorio_id, cantidad, etiqueta)] en el orden del Treeview
        super().__init__(parent)

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=20)
        self._modelos()
        self._chips_modelos()
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
        ultima = ingresos.ultima_sucursal()   # la del último IMEI cargado
        self.sucursal.set(next((label for label, i in self.sucursales.items() if i == ultima), ""))

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

        chip_add = ttk.Frame(card, style="Inner.TFrame")
        chip_add.pack(fill="x", pady=(16, 8))
        ttk.Label(chip_add, text="Chips (sin IMEI: Claro los manda junto con el pedido, pero sin un número de "
                                 "serie que valga la pena cargar en el stock; el primero y el último son solo "
                                 "para el remito que se le manda a administración)", style="Card.TLabel"
                  ).grid(row=0, column=0, columnspan=5, sticky="w")
        for col, texto in enumerate(("Tipo de SIM", "Cantidad", "Primer chip", "Último chip")):
            ttk.Label(chip_add, text=texto, style="Card.TLabel").grid(row=1, column=col, sticky="w",
                                                                      padx=(0 if col == 0 else 16, 0), pady=(6, 0))
        self.chip_tipo, self.chip_cantidad = tk.StringVar(), tk.StringVar()
        self.chip_primero, self.chip_ultimo = tk.StringVar(), tk.StringVar()
        self.cmb_chip = Combobox(chip_add, textvariable=self.chip_tipo, values=self.chip_labels, width=32)
        self.cmb_chip.grid(row=2, column=0, sticky="w")
        self.entry_chip = ttk.Entry(chip_add, textvariable=self.chip_cantidad, width=10)
        self.entry_chip.grid(row=2, column=1, padx=(16, 0), sticky="w")
        self.entry_chip_primero = ttk.Entry(chip_add, textvariable=self.chip_primero, width=16)
        self.entry_chip_primero.grid(row=2, column=2, padx=(16, 0), sticky="w")
        self.entry_chip_ultimo = ttk.Entry(chip_add, textvariable=self.chip_ultimo, width=16)
        self.entry_chip_ultimo.grid(row=2, column=3, padx=(16, 0), sticky="w")
        ttk.Button(chip_add, text="Agregar", command=self._agregar_chip).grid(row=2, column=4, padx=(12, 0))
        ttk.Button(chip_add, text="Quitar seleccionado", command=self._quitar_chip).grid(row=2, column=5, padx=(8, 0))
        self.error_chip = ttk.Label(chip_add, text="", foreground=theme.DANGER, style="Card.TLabel")
        self.error_chip.grid(row=3, column=0, columnspan=6, sticky="w", pady=(6, 0))
        for w in (self.cmb_chip, self.entry_chip, self.entry_chip_primero, self.entry_chip_ultimo):
            w.bind("<Return>", self._agregar_chip)

        chip_wrap = ttk.Frame(card, style="Inner.TFrame")
        chip_wrap.pack(fill="x")
        self.tree_chips = ttk.Treeview(chip_wrap, columns=("tipo", "cantidad", "primero", "ultimo"),
                                       show="headings", selectmode="browse", height=4)
        for col, texto, ancho, anchor in (("tipo", "Tipo de SIM", 260, "w"), ("cantidad", "Cantidad", 90, "center"),
                                          ("primero", "Primer chip", 150, "center"),
                                          ("ultimo", "Último chip", 150, "center")):
            self.tree_chips.heading(col, text=texto, anchor=anchor)
            self.tree_chips.column(col, width=ancho, minwidth=60, stretch=col == "tipo", anchor=anchor)
        self.tree_chips.pack(fill="x")
        self.tree_chips.tag_configure("odd", background=theme.ZEBRA)
        self.tree_chips.bind("<Delete>", lambda e: self._quitar_chip())

        self.entry.focus_set()

    def build_actions(self, bar):
        self.btn_registrar = ttk.Button(bar, text="Registrar ingreso", style="Accent.TButton", command=self._registrar)
        self.btn_registrar.pack(side="right")
        ttk.Button(bar, text="Exportar Excel (equipos)", command=self._exportar).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="Exportar Excel (chips)", command=self._exportar_chips).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="Limpiar", command=self._limpiar).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="Quitar seleccionado", command=self._quitar).pack(side="left")
        self.count = ttk.Label(bar, style="Sub.TLabel")
        self.count.pack(side="left", padx=16)
        self._refresh()
        self._refresh_chips()

    # --- modelos -------------------------------------------------------
    def _modelos(self):
        """Equipos de verdad (los chips, marca SIM, van aparte: se cargan por cantidad, no por IMEI)."""
        options = [(r["id"], f"{r['codigo']} - {r['descripcion']}") for r in stock.equipos.list() if r["marca"] != "SIM"]
        self.modelos = {label: i for i, label in options}
        self.labels = [label for _, label in options]

    def _chips_modelos(self):
        """Chips (equipos marca SIM), sin los virtuales: la E-SIM no llega en una caja de Claro."""
        rows = [r for r in stock.equipos.list("", "SIM") if not r["virtual"]]
        self.chip_ids = {f"{r['codigo']} - {r['descripcion']}": r["id"] for r in rows}
        self.chip_labels = list(self.chip_ids)

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
        if (self.items or self.chips) and not messagebox.askyesno(
                "Limpiar", "¿Vaciar la lista de equipos y chips cargados?", parent=self.winfo_toplevel()):
            return
        self.items.clear()
        self.chips.clear()
        self._refresh()
        self._refresh_chips()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for n, (imei, _, modelo) in enumerate(self.items, start=1):
            self.tree.insert("", "end", values=(n, imei, modelo), tags=("odd",) if n % 2 == 0 else ())
        modelos = len({e for _, e, _ in self.items})
        self.count.config(text=f"{len(self.items)} equipos · {modelos} modelo{'' if modelos == 1 else 's'}")

    # --- chips -----------------------------------------------------------
    def _resolver_chip(self):
        """El id del tipo de SIM escrito o elegido; si lo escrito coincide con uno solo, ese. None si no se puede."""
        text = self.chip_tipo.get().strip()
        if text in self.chip_ids:
            return self.chip_ids[text]
        tokens = text.upper().split()
        found = [l for l in self.chip_labels if tokens and all(t in l.upper() for t in tokens)]
        if len(found) == 1:
            self.chip_tipo.set(found[0])
            return self.chip_ids[found[0]]
        return None

    def _agregar_chip(self, event=None):
        accesorio_id = self._resolver_chip()
        if accesorio_id is None:
            self.error_chip.config(text="Elegí el tipo de SIM de la lista.")
            self.cmb_chip.focus_set()
            return "break"
        try:
            cantidad = int(self.chip_cantidad.get().strip())
            if cantidad <= 0:
                raise ValueError
        except ValueError:
            self.error_chip.config(text="La cantidad tiene que ser un número entero mayor a 0.")
            self.entry_chip.focus_set()
            return "break"
        etiqueta = self.chip_tipo.get().strip()
        if any(a == accesorio_id for a, _, _, _, _ in self.chips):
            self.error_chip.config(text=f"{etiqueta} ya está en la lista: quitalo si querés cambiar algo.")
            return "break"
        primero, ultimo = self.chip_primero.get().strip(), self.chip_ultimo.get().strip()
        self.chips.append((accesorio_id, cantidad, etiqueta, primero, ultimo))
        self.error_chip.config(text="")
        self.chip_tipo.set("")
        self.chip_cantidad.set("")
        self.chip_primero.set("")
        self.chip_ultimo.set("")
        self._refresh_chips()
        self.cmb_chip.focus_set()
        return "break"

    def _quitar_chip(self):
        sel = self.tree_chips.selection()
        if sel:
            del self.chips[self.tree_chips.index(sel[0])]
            self._refresh_chips()

    def _refresh_chips(self):
        self.tree_chips.delete(*self.tree_chips.get_children())
        for n, (_, cantidad, etiqueta, primero, ultimo) in enumerate(self.chips, start=1):
            self.tree_chips.insert("", "end", values=(etiqueta, cantidad, primero, ultimo),
                                   tags=("odd",) if n % 2 == 0 else ())

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
        if not self.items and not self.chips:
            return messagebox.showwarning("Ingreso de equipos", "No hay equipos ni chips en la lista.", parent=top)
        sucursal_id, pedido, fecha = cab
        try:
            modelos, lineas_chips = ingresos.registrar(pedido, sucursal_id, fecha, [(i, e) for i, e, _ in self.items],
                                                        [(a, c) for a, c, _, _, _ in self.chips])
        except ValueError as e:
            return messagebox.showerror("No se pudo registrar", str(e), parent=top)
        partes = []
        if self.items:
            partes.append(f"{len(self.items)} IMEI de {modelos} modelo{'' if modelos == 1 else 's'}")
        if self.chips:
            total_chips = sum(c for _, c, _, _, _ in self.chips)
            partes.append(f"{total_chips} chip{'' if total_chips == 1 else 's'} de {lineas_chips} tipo{'' if lineas_chips == 1 else 's'}")
        messagebox.showinfo("Ingreso registrado", f"Se cargaron {' y '.join(partes)}, y se sumó el stock en "
                            f"{self.sucursal.get().split(' - ')[0]}.", parent=top)
        if self.items and messagebox.askyesno("Exportar", "¿Querés guardar el pedido de equipos en Excel?", parent=top):
            self._exportar()
        if self.chips and messagebox.askyesno("Exportar", "¿Querés guardar el remito de chips en Excel, para "
                                              "administración?", parent=top):
            self._exportar_chips()
        self.items.clear()
        self.chips.clear()
        self.pedido.set("")
        self._refresh()
        self._refresh_chips()

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

    def _exportar_chips(self):
        top = self.winfo_toplevel()
        if not self.chips:
            return messagebox.showwarning("Exportar", "No hay chips en la lista.", parent=top)
        pedido = self.pedido.get().strip() or "sin numero"
        path = filedialog.asksaveasfilename(
            parent=top, title="Guardar remito de chips", defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialdir=escritorio(), initialfile=f"CHIPS {NOMBRE_INVALIDO.sub('_', pedido)}.xlsx")
        if not path:
            return
        destino = self.sucursal.get().split(" - ")[0]
        try:
            remito_xlsx.generar_chips(path, destino, pedido,
                                      [(etiqueta.split(" - ", 1)[-1], primero, ultimo, cantidad)
                                       for _, cantidad, etiqueta, primero, ultimo in self.chips])
        except ImportError:
            return messagebox.showerror("Falta openpyxl", "Para guardar en Excel hace falta instalar openpyxl.", parent=top)
        except OSError as e:
            return messagebox.showerror("No se pudo guardar", str(e), parent=top)
        messagebox.showinfo("Exportar", f"Se guardó {Path(path).name}.", parent=top)
