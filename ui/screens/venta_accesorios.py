"""Nuevo > Accesorios: una venta con varios productos y pagos combinados."""
import tkinter as tk
from tkinter import messagebox, ttk

from db import refs, stock, ventas
from ui import entry_helpers, theme
from ui.autocomplete import Combobox
from ui.base import Screen
from ui.formatting import fmt_datetime, fmt_int, fmt_money, money_to_input, now_iso, parse_datetime, parse_int, parse_money

CLIENTE = "CONSUMIDOR FINAL"


class Accesorios(Screen):
    title = "Nueva venta · Accesorios"
    subtitle = "Una venta con uno o varios accesorios y uno o varios pagos: descuenta el stock y queda en la caja"

    def __init__(self, parent):
        self.items = []   # [(producto_id, texto, cantidad, precio)] en el orden de la tabla
        self.pagos = []   # [(cuenta_id, monto, interes)]
        super().__init__(parent)

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        self._cargar_listas()

        head = ttk.Frame(card, style="Inner.TFrame")
        head.pack(fill="x")
        self.fecha, self.sucursal, self.vendedor = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.cliente, self.cupon, self.factura = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.combos = []   # los desplegables de sucursal y vendedor
        for col, (text, var, kind, width) in enumerate((
                ("Fecha y hora", self.fecha, "entry", 15), ("Sucursal", self.sucursal, "sucursal", 17),
                ("Vendedor", self.vendedor, "vendedor", 19), ("Cliente", self.cliente, "text", 19),
                ("Nº cupón", self.cupon, "text", 8), ("Factura", self.factura, "text", 10))):
            ttk.Label(head, text=text, style="Card.TLabel").grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 12, 0))
            if kind in ("sucursal", "vendedor"):
                options = self.opciones[kind]
                w = Combobox(head, textvariable=var, values=list(options), state="readonly", width=width)
                self.combos.append(w)
            else:
                w = ttk.Entry(head, textvariable=var, width=width)
                if kind == "text":
                    entry_helpers.force_upper(w)
            w.grid(row=1, column=col, sticky="w", padx=(0 if col == 0 else 12, 0))

        body = ttk.Frame(card, style="Inner.TFrame")
        body.pack(fill="both", expand=True, pady=(14, 0))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2, minsize=350)
        body.rowconfigure(0, weight=1)
        left = ttk.Frame(body, style="Inner.TFrame")
        left.grid(row=0, column=0, sticky="nsew")
        right = ttk.Frame(body, style="Inner.TFrame")
        right.grid(row=0, column=1, sticky="nsew", padx=(20, 0))
        self._build_productos(left)
        self._build_pagos(right)

    def _build_productos(self, parent):
        ttk.Label(parent, text="Productos", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w")
        add = ttk.Frame(parent, style="Inner.TFrame")
        add.pack(fill="x", pady=(6, 0))
        ttk.Label(add, text="Producto (escribí código o descripción)", style="Card.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(add, text="Cant.", style="Card.TLabel").grid(row=0, column=1, sticky="w", padx=(10, 0))
        ttk.Label(add, text="Precio unit.", style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(10, 0))
        self.producto, self.cantidad, self.precio = tk.StringVar(), tk.StringVar(value="1"), tk.StringVar()
        self.cmb = Combobox(add, textvariable=self.producto, values=self.labels, width=24)
        self.cmb.grid(row=1, column=0, sticky="ew")
        self.e_cant = ttk.Entry(add, textvariable=self.cantidad, width=6, justify="right")
        self.e_cant.grid(row=1, column=1, padx=(10, 0))
        self.e_precio = ttk.Entry(add, textvariable=self.precio, width=10)
        self.e_precio.grid(row=1, column=2, padx=(10, 0))
        ttk.Button(add, text="Agregar", style="Accent.TButton", command=self._agregar).grid(row=1, column=3, padx=(10, 0))
        add.columnconfigure(0, weight=1)
        self.info = ttk.Label(add, text="", style="Muted.TLabel")
        self.info.grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.error = ttk.Label(add, text="", foreground=theme.DANGER, style="Card.TLabel")
        self.error.grid(row=3, column=0, columnspan=4, sticky="w")
        self.cmb.bind("<<ComboboxSelected>>", lambda e: self._elegido(avanzar=True))
        self.cmb.bind("<Return>", lambda e: self._elegido(avanzar=True))
        self.e_cant.bind("<Return>", lambda e: self._agregar())
        self.e_precio.bind("<Return>", lambda e: self._agregar())

        wrap = ttk.Frame(parent, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True, pady=(6, 0))
        self.tree = ttk.Treeview(wrap, columns=("n", "producto", "cant", "precio", "subtotal"), show="headings",
                                 selectmode="browse")
        for col, text, width, stretch, anchor in (("n", "#", 36, False, "center"), ("producto", "Producto", 300, True, "w"),
                                                  ("cant", "Cant.", 55, False, "center"),
                                                  ("precio", "Precio unit.", 100, False, "e"),
                                                  ("subtotal", "Subtotal", 110, False, "e")):
            self.tree.heading(col, text=text, anchor=anchor)
            self.tree.column(col, width=width, minwidth=40, stretch=stretch, anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.bind("<Delete>", lambda e: self._quitar())

    def _build_pagos(self, parent):
        ttk.Label(parent, text="Pagos", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w")
        add = ttk.Frame(parent, style="Inner.TFrame")
        add.pack(fill="x", pady=(6, 0))
        for col, text in enumerate(("Cuenta", "Monto", "Cobrado c/interés")):
            ttk.Label(add, text=text, style="Card.TLabel").grid(row=0, column=col, sticky="w", padx=(0 if col == 0 else 8, 0))
        self.cuenta, self.monto, self.cobrado = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.cmb_cuenta = Combobox(add, textvariable=self.cuenta, values=list(self.cuentas), state="readonly", width=11)
        self.cmb_cuenta.grid(row=1, column=0, sticky="w")
        self.e_monto = ttk.Entry(add, textvariable=self.monto, width=10)
        self.e_monto.grid(row=1, column=1, padx=(8, 0))
        self.e_cobrado = ttk.Entry(add, textvariable=self.cobrado, width=10)
        self.e_cobrado.grid(row=1, column=2, padx=(8, 0))
        ttk.Button(add, text="Agregar", command=self._agregar_pago).grid(row=1, column=3, padx=(8, 0))
        ttk.Label(parent, text="Con tarjeta en cuotas: dejá en Monto la parte de la venta y en Cobrado lo que cobró el "
                  "posnet; la diferencia son los intereses y en la caja van aparte.", style="Muted.TLabel",
                  wraplength=330, justify="left").pack(anchor="w", pady=(4, 0))
        self.error_pago = ttk.Label(parent, text="", foreground=theme.DANGER, style="Card.TLabel", wraplength=330)
        self.error_pago.pack(anchor="w")
        self.cmb_cuenta.bind("<<ComboboxSelected>>", lambda e: self._sugerir_monto())
        self.e_monto.bind("<Return>", lambda e: self._agregar_pago())
        self.e_cobrado.bind("<Return>", lambda e: self._agregar_pago())

        wrap = ttk.Frame(parent, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True, pady=(6, 0))
        self.tree_pagos = ttk.Treeview(wrap, columns=("cuenta", "monto", "interes"), show="headings", selectmode="browse",
                                       height=4)
        for col, text, width, anchor in (("cuenta", "Cuenta", 120, "w"), ("monto", "Monto", 110, "e"),
                                         ("interes", "Interés", 100, "e")):
            self.tree_pagos.heading(col, text=text, anchor=anchor)
            self.tree_pagos.column(col, width=width, minwidth=40, stretch=col == "cuenta", anchor=anchor)
        self.tree_pagos.pack(fill="both", expand=True)
        self.tree_pagos.tag_configure("odd", background=theme.ZEBRA)
        self.tree_pagos.bind("<Delete>", lambda e: self._quitar_pago())
        foot = ttk.Frame(parent, style="Inner.TFrame")
        foot.pack(fill="x", pady=(6, 0))
        ttk.Button(foot, text="Quitar pago", command=self._quitar_pago).pack(side="left")
        self.resumen = ttk.Label(parent, text="", style="Card.TLabel", font=("Segoe UI", 12, "bold"), justify="right")
        self.resumen.pack(anchor="e", pady=(10, 0))
        self.resumen_pagos = ttk.Label(parent, text="", style="Muted.TLabel", justify="right")
        self.resumen_pagos.pack(anchor="e")

    def build_actions(self, bar):
        ttk.Button(bar, text="Guardar venta", style="Accent.TButton", command=self._guardar).pack(side="right")
        ttk.Button(bar, text="Limpiar", command=self._limpiar).pack(side="right", padx=(0, 8))
        ttk.Button(bar, text="Quitar producto", command=self._quitar).pack(side="left")
        self.count = ttk.Label(bar, style="Sub.TLabel")
        self.count.pack(side="left", padx=16)
        self._reset(keep_header=False)
        self.cmb.focus_set()

    # --- listas --------------------------------------------------------
    def _cargar_listas(self):
        productos = stock.accesorios.list()
        self.productos = {f"{p['codigo']} - {p['descripcion']}": p for p in productos}
        self.labels = list(self.productos)
        self.mayus = [label.upper() for label in self.labels]
        self.opciones = {"sucursal": {label: i for i, label in refs.choices("sucursales")},
                         "vendedor": {label: i for i, label in refs.choices("empleados")}}
        self.cuentas = {codigo: i for i, codigo in refs.codigos("cuentas")}

    def _coincidencias(self, texto):
        tokens = texto.upper().split()
        return [l for l, m in zip(self.labels, self.mayus) if all(t in m for t in tokens)]

    def _resolver(self):
        """El producto escrito o elegido: la fila de accesorios, o None si no hay uno solo que coincida."""
        texto = self.producto.get().strip()
        if texto in self.productos:
            return texto, self.productos[texto]
        if not texto:
            return None
        exactos = [l for l in self.labels if l.split(" - ", 1)[0].upper() == texto.upper()]   # el código, tal cual
        encontrados = exactos or self._coincidencias(texto)
        if len(encontrados) == 1:
            self.producto.set(encontrados[0])
            return encontrados[0], self.productos[encontrados[0]]
        return None

    def _elegido(self, avanzar=False):
        """Al elegir el producto: propone el precio minorista y muestra el stock."""
        found = self._resolver()
        if not found:
            self.info.config(text="")
            if avanzar:
                self.error.config(text="Elegí un producto de la lista (o escribí algo que coincida con uno solo).")
            return "break"
        _, p = found
        self.error.config(text="")
        self.precio.set(money_to_input(p["precio_minorista"]) if p["precio_minorista"] else "")
        self.info.config(text="Sin stock (virtual)" if p["virtual"] else f"Stock: {fmt_int(p['stock'])}")
        if avanzar:
            self.e_cant.focus_set()
            self.e_cant.select_range(0, "end")
        return "break"

    # --- productos -----------------------------------------------------
    def _agregar(self):
        found = self._resolver()
        if not found:
            self.error.config(text="Elegí un producto de la lista.")
            self.cmb.focus_set()
            return
        texto, p = found
        try:
            cantidad = parse_int(self.cantidad.get())
            precio = parse_money(self.precio.get())
        except ValueError:
            self.error.config(text="Cantidad y precio tienen que ser números.")
            return
        if cantidad <= 0:
            self.error.config(text="La cantidad tiene que ser mayor a 0.")
            self.e_cant.focus_set()
            return
        for n, (pid, t, c, pr) in enumerate(self.items):   # el mismo producto al mismo precio se suma a su fila
            if pid == p["id"] and pr == precio:
                self.items[n] = (pid, t, c + cantidad, pr)
                break
        else:
            self.items.append((p["id"], texto, cantidad, precio))
        self.error.config(text="")
        self.producto.set("")
        self.cantidad.set("1")
        self.precio.set("")
        self.info.config(text="")
        self._refresh()
        self.cmb.focus_set()

    def _quitar(self):
        sel = self.tree.selection()
        if sel:
            del self.items[self.tree.index(sel[0])]
            self._refresh()

    # --- pagos ---------------------------------------------------------
    def _total(self):
        return round(sum(c * pr for _, _, c, pr in self.items), 2)

    def _pagado(self):
        return round(sum(m for _, m, _ in self.pagos), 2)

    def _sugerir_monto(self):
        """Al elegir la cuenta, propone lo que falta pagar."""
        falta = round(self._total() - self._pagado(), 2)
        if not self.monto.get().strip() and falta > 0:
            self.monto.set(money_to_input(falta))
        self.e_monto.focus_set()
        self.e_monto.select_range(0, "end")

    def _agregar_pago(self):
        self.cmb_cuenta.confirmar()
        if self.cuenta.get() not in self.cuentas:
            self.error_pago.config(text="Elegí la cuenta.")
            return
        try:
            monto = parse_money(self.monto.get())
            cobrado = parse_money(self.cobrado.get()) or monto   # vacío: se cobró justo el monto
        except ValueError:
            self.error_pago.config(text="Monto y cobrado tienen que ser números.")
            return
        if monto <= 0:
            self.error_pago.config(text="El monto tiene que ser mayor a 0.")
            return
        if cobrado < monto:
            self.error_pago.config(text="Lo cobrado no puede ser menos que el monto.")
            return
        self.pagos.append((self.cuentas[self.cuenta.get()], monto, round(cobrado - monto, 2)))
        self.cuenta.set("")
        self.monto.set("")
        self.cobrado.set("")
        self.error_pago.config(text="")
        self._refresh()
        self.cmb_cuenta.focus_set()

    def _quitar_pago(self):
        sel = self.tree_pagos.selection()
        if sel:
            del self.pagos[self.tree_pagos.index(sel[0])]
            self._refresh()

    # --- pantalla ------------------------------------------------------
    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for n, (_, texto, cantidad, precio) in enumerate(self.items, start=1):
            self.tree.insert("", "end", values=(n, texto, fmt_int(cantidad), fmt_money(precio), fmt_money(cantidad * precio)),
                             tags=("odd",) if n % 2 == 0 else ())
        nombres = {i: codigo for codigo, i in self.cuentas.items()}
        self.tree_pagos.delete(*self.tree_pagos.get_children())
        for n, (cuenta_id, monto, interes) in enumerate(self.pagos, start=1):
            self.tree_pagos.insert("", "end", values=(nombres.get(cuenta_id, "?"), fmt_money(monto),
                                                      fmt_money(interes) if interes else ""),
                                   tags=("odd",) if n % 2 == 0 else ())
        total, pagado = self._total(), self._pagado()
        self.resumen.config(text=f"Total  {fmt_money(total)}")
        falta = round(total - pagado, 2)
        intereses = round(sum(i for _, _, i in self.pagos), 2)
        self.resumen_pagos.config(
            text=f"Pagado {fmt_money(pagado)}" + (f" · Falta {fmt_money(falta)}" if falta > 0 else "")
            + (f" · Pasado {fmt_money(-falta)}" if falta < 0 else "")
            + (f" · Intereses {fmt_money(intereses)}" if intereses else ""),
            foreground=theme.DANGER if self.items and falta != 0 else theme.MUTED)
        unidades = sum(c for _, _, c, _ in self.items)
        self.count.config(text=f"{len(self.items)} producto{'' if len(self.items) == 1 else 's'} · "
                               f"{fmt_int(unidades)} unidad{'' if unidades == 1 else 'es'}")

    def _reset(self, keep_header=True):
        """Deja la pantalla lista para otra venta. Sucursal y vendedor se conservan (o, la primera vez, los de la última venta)."""
        self.items.clear()
        self.pagos.clear()
        if not keep_header:
            sucursal_id, vendedor_id = ventas.ultimos_datos()
            for var, options, wanted in ((self.sucursal, self.opciones["sucursal"], sucursal_id),
                                         (self.vendedor, self.opciones["vendedor"], vendedor_id)):
                var.set(next((label for label, i in options.items() if i == wanted), ""))
        self.fecha.set(fmt_datetime(now_iso()))
        self.cliente.set(CLIENTE)
        self.cupon.set("")
        self.factura.set("")
        self.producto.set("")
        self.cantidad.set("1")
        self.precio.set("")
        self.cuenta.set("")
        self.monto.set("")
        self.cobrado.set("")
        self.info.config(text="")
        self.error.config(text="")
        self.error_pago.config(text="")
        self._refresh()

    def _limpiar(self):
        if (self.items or self.pagos) and not messagebox.askyesno(
                "Limpiar", "¿Vaciar la venta que estás cargando?", parent=self.winfo_toplevel()):
            return
        self._reset()
        self.cmb.focus_set()

    # --- guardar -------------------------------------------------------
    def _guardar(self):
        top = self.winfo_toplevel()

        def aviso(texto):
            messagebox.showwarning("Venta de accesorios", texto, parent=top)

        for combo in self.combos:
            combo.confirmar()
        try:
            fecha = parse_datetime(self.fecha.get())
        except ValueError:
            return aviso("Fecha y hora: usá el formato dd/mm/aaaa hh:mm.")
        if self.sucursal.get() not in self.opciones["sucursal"]:
            return aviso("Elegí la sucursal.")
        if self.vendedor.get() not in self.opciones["vendedor"]:
            return aviso("Elegí el vendedor.")
        if not self.items:
            return aviso("Agregá al menos un producto.")
        total, pagado = self._total(), self._pagado()
        if not self.pagos:
            return aviso("Agregá al menos un pago.")
        if pagado != total:
            return aviso(f"Los pagos suman {fmt_money(pagado)} y la venta es de {fmt_money(total)}: "
                         "el monto de los pagos tiene que ser igual al total (los intereses van aparte, en Cobrado).")
        items = [(pid, cantidad, precio) for pid, _, cantidad, precio in self.items]
        faltan = ventas.faltantes(items)
        if faltan:
            detalle = "\n".join(f"    {texto}: de {fmt_int(hoy)} a {fmt_int(queda)}" for texto, hoy, queda in faltan)
            if not messagebox.askyesno("Stock insuficiente", f"El stock quedaría en negativo:\n\n{detalle}\n\n¿Registrar igual?",
                                       icon="warning", parent=top):
                return
        cab = {"fecha": fecha, "cliente": self.cliente.get().strip() or CLIENTE,
               "vendedor_id": self.opciones["vendedor"][self.vendedor.get()],
               "sucursal_id": self.opciones["sucursal"][self.sucursal.get()],
               "cupon": self.cupon.get().strip(), "factura": self.factura.get().strip()}
        try:
            venta_id = ventas.registrar(cab, items, self.pagos)
        except ValueError as e:
            return messagebox.showerror("No se pudo registrar", str(e), parent=top)
        messagebox.showinfo("Venta registrada", f"Venta {venta_id} · {fmt_money(total)}\n"
                            f"{len(items)} producto{'' if len(items) == 1 else 's'}, con el stock ya descontado.", parent=top)
        self._cargar_listas()   # el stock cambió
        self.cmb["values"] = self.labels   # con el stock ya actualizado
        self._reset()
        self.cmb.focus_set()
