"""Ventanita modal con un formulario generado a partir de una lista de Field."""
import re
import tkinter as tk
from tkinter import ttk

from ui import entry_helpers, theme
from ui.autocomplete import Combobox
from ui.formatting import (fmt_date, fmt_datetime, fmt_money, money_to_input, now_iso, parse_date,
                           parse_datetime, parse_int, parse_money)


class FormDialog(tk.Toplevel):
    """`on_save(data, dialog)` devuelve un mensaje de error (la ventana queda abierta) o None (se cierra).

    `defaults`: en un alta, valor inicial de los campos select ({campo: id}), p. ej. el último usado.
    `suggestions`: {campo select: (campo destino, {id: precio})}; al elegir, propone el precio en el
    destino si está vacío o si tiene el precio propuesto antes (nunca pisa lo que se escribió a mano).
    `columns`: en cuántas columnas de campos se reparte el formulario (para los muy largos; con más de 1
    no se pueden usar los campos multi ni pagos).
    """

    def __init__(self, parent, title, fields, values=None, choices=None, on_save=None, defaults=None,
                 suggestions=None, columns=1):
        super().__init__(parent, bg=theme.BG)
        fields = [f for f in fields if f.kind != "calc"]   # las calculadas solo van en la tabla
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.fields = fields
        self.values = values
        self.on_save = on_save
        self.vars, self.widgets = {}, {}
        self.select_ids = {}   # campo select -> {texto mostrado: id}
        self.multi_ids = {}    # campo multi -> [ids] en el orden de la lista
        self.multi_boxes = {}
        self.pagos = {}        # campo pagos -> [(id de cuenta, monto)] cargados hasta ahora
        self.pago_vars = {}    # campo pagos -> (cuenta, monto) escritos y todavía sin agregar
        choices = choices or {}

        body = ttk.Frame(self, padding=(28, 22, 28, 4))
        body.pack(fill="both")
        ttk.Label(body, text=title, style="Title.TLabel", font=("Segoe UI", 14, "bold")
                  ).grid(row=0, column=0, columnspan=2 * columns, sticky="w", pady=(0, 12))

        ew = 34 if columns == 1 else 24   # ancho de los campos
        for n, f in enumerate(fields):
            r, lc = n // columns + 1, n % columns * 2   # fila y columna del rótulo; el campo va en lc + 1
            label = ttk.Frame(body)
            ttk.Label(label, text=f.label).pack(side="left")
            if f.required:
                ttk.Label(label, text=" *", foreground=theme.DANGER).pack(side="left")
            label.grid(row=r, column=lc, sticky="nw" if f.kind == "pagos" else "w",
                       padx=(0 if lc == 0 else 28, 18), pady=(9, 6) if f.kind == "pagos" else 6)
            if f.kind == "pagos":
                self._build_pagos(body, r, f, values.get(f.key, []) if values else [], choices.get(f.key, []))
                continue
            if f.kind == "multi":
                self._build_multi(body, r, f, choices.get(f.key, []), values.get(f.key, []) if values else [])
                continue
            if f.kind == "select":
                options = list(choices.get(f.key, []))   # [(id, texto)]
                current = values.get(f.key) if values else (defaults or {}).get(f.key)
                if current is not None and all(i != current for i, _ in options):
                    options.append((current, values.get(f.key + "_label", str(current))))  # dado de baja
                self.select_ids[f.key] = {label: i for i, label in options}
                shown = next((label for i, label in options if i == current), "")
                var = tk.StringVar(value=shown)
                w = Combobox(body, textvariable=var, values=[label for _, label in options],
                             state="readonly", width=ew)
                w.grid(row=r, column=lc + 1, sticky="ew")
                self.vars[f.key], self.widgets[f.key] = var, w
                if f.key in (suggestions or {}):
                    self._suggest_on_select(f, w, var, *suggestions[f.key])
                continue
            var = tk.StringVar(value=self._initial(f, values))
            if f.kind == "list":
                allowed = list(f.options) if f.required else [""] + list(f.options)   # sin elegir, si es opcional
                w = Combobox(body, textvariable=var, values=allowed, state="readonly", width=ew)
                w.grid(row=r, column=lc + 1, sticky="ew")
                self.vars[f.key], self.widgets[f.key] = var, w
                continue
            if f.kind == "bool":
                w = ttk.Checkbutton(body, variable=var, onvalue="1", offvalue="0",
                                    command=lambda f=f: self._toggle(f))
                w.grid(row=r, column=lc + 1, sticky="w")
                self.vars[f.key], self.widgets[f.key] = var, w
                continue
            if f.kind == "choice":
                w = Combobox(body, textvariable=var, values=choices.get(f.key, []), width=ew)
            else:
                w = ttk.Entry(body, textvariable=var, width=ew + 2,
                              justify="right" if f.kind == "int" else "left")   # los montos, a la izquierda
            w.grid(row=r, column=lc + 1, sticky="ew")
            if f.kind in ("text", "choice"):
                entry_helpers.force_upper(w)
            entry_helpers.Undo(w, var)
            self.vars[f.key], self.widgets[f.key] = var, w

        for f in fields:
            if f.kind == "bool":
                self._toggle(f, keep=True)

        self.error = ttk.Label(body, text="", foreground=theme.DANGER, wraplength=380 * columns)
        self.error.grid(row=(len(fields) - 1) // columns + 2, column=0, columnspan=2 * columns, sticky="w",
                        pady=(10, 0))

        bar = ttk.Frame(self, padding=(28, 8, 28, 22))
        bar.pack(fill="x")
        ttk.Label(bar, text="*", foreground=theme.DANGER, font=theme.FONT_BOLD).pack(side="left")
        ttk.Label(bar, text=" Obligatorio", style="Sub.TLabel").pack(side="left")
        ttk.Button(bar, text="Guardar", style="Accent.TButton", command=self._save).pack(side="right")
        ttk.Button(bar, text="Cancelar", command=self.destroy).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda e: self._save())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 3
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.wait_visibility()
        self.grab_set()
        next(self.widgets[f.key] for f in fields if f.kind != "datetime").focus_set()

    def _build_multi(self, body, row, field, options, selected):
        """Lista con varias opciones a la vez (un clic tilda / destilda). `options`: [(id, texto)]."""
        holder = ttk.Frame(body)
        holder.grid(row=row, column=1, sticky="w")
        box = tk.Listbox(holder, selectmode="multiple", exportselection=False, activestyle="none",
                         height=min(max(len(options), 3), 6), width=38, font=theme.FONT, bd=1,
                         relief="solid", highlightthickness=0, selectbackground=theme.ACCENT,
                         selectforeground="white")
        for i, (oid, label) in enumerate(options):
            box.insert("end", label)
            if oid in selected:
                box.selection_set(i)
        box.pack(side="left")
        if len(options) > 6:
            bar = ttk.Scrollbar(holder, orient="vertical", command=box.yview)
            box.configure(yscrollcommand=bar.set)
            bar.pack(side="left", fill="y")
        self.multi_ids[field.key] = [oid for oid, _ in options]
        self.multi_boxes[field.key] = box
        self.widgets[field.key] = box

    def _suggest_on_select(self, field, box, var, target, prices):
        last = [None]   # el último precio propuesto: mientras el destino lo tenga, se puede reemplazar

        def on_select(event=None):
            price = prices.get(self.select_ids[field.key].get(var.get()))
            dest = self.vars.get(target)
            if price and dest is not None and dest.get().strip() in ("", last[0]):
                last[0] = money_to_input(price)
                dest.set(last[0])

        box.bind("<<ComboboxSelected>>", on_select)

    def _build_pagos(self, body, row, field, initial, options):
        """Pagos combinados: se elige la cuenta y el monto, «Agregar», y se puede agregar otro.

        `options`: [(id, código)] de las cuentas; `initial`: [(id, monto, código)] de lo ya guardado.
        """
        nombres = {cid: codigo for cid, codigo in options}
        nombres.update({cid: codigo for cid, _, codigo in initial})   # también las cuentas dadas de baja
        ids = {codigo: cid for cid, codigo in options}
        pagos = self.pagos[field.key] = [(cid, monto) for cid, monto, _ in initial]
        holder = ttk.Frame(body)
        holder.grid(row=row, column=1, sticky="ew")
        top = ttk.Frame(holder)
        top.pack(fill="x")
        cuenta, monto = tk.StringVar(), tk.StringVar()
        self.pago_vars[field.key] = (cuenta, monto)
        box = Combobox(top, textvariable=cuenta, values=[codigo for _, codigo in options],
                       state="readonly", width=16)
        box.pack(side="left")
        entry = ttk.Entry(top, textvariable=monto, width=13)
        entry.pack(side="left", padx=6)
        ttk.Button(top, text="Agregar", command=lambda: agregar()).pack(side="left")
        lista = tk.Listbox(holder, height=3, activestyle="none", exportselection=False, font=theme.FONT,
                           bd=1, relief="solid", highlightthickness=0, selectbackground=theme.ACCENT,
                           selectforeground="white", width=38)
        lista.pack(fill="x", pady=(6, 0))
        foot = ttk.Frame(holder)
        foot.pack(fill="x", pady=(4, 0))
        ttk.Button(foot, text="Quitar", command=lambda: quitar()).pack(side="left")
        resumen = ttk.Label(foot, style="Sub.TLabel")
        resumen.pack(side="right")

        def total():
            try:
                return parse_money(self.vars[field.total].get()) if field.total in self.vars else 0.0
            except ValueError:
                return 0.0

        def pagado():
            return round(sum(m for _, m in pagos), 2)

        def refresh():
            lista.delete(0, "end")
            for cid, v in pagos:
                lista.insert("end", f"{nombres.get(cid, '?')}   ·   {fmt_money(v)}")
            resumen.config(text=f"Pagado {fmt_money(pagado())} de {fmt_money(total())}",
                           foreground=theme.DANGER if pagos and pagado() != total() else theme.MUTED)

        def agregar(event=None):
            box.confirmar()   # lo escrito en la cuenta se completa con la opción que corresponde
            try:
                valor = parse_money(monto.get())
            except ValueError:
                valor = 0
            if cuenta.get() not in ids or valor <= 0:
                self.error.config(text="Pagos: elegí la cuenta y un monto mayor a 0.")
                return "break"
            pagos.append((ids[cuenta.get()], valor))
            cuenta.set("")
            monto.set("")
            self.error.config(text="")
            refresh()
            box.focus_set()
            return "break"

        def quitar():
            for i in reversed(lista.curselection()):
                del pagos[i]
            refresh()

        def sugerir(event=None):   # al elegir la cuenta, propone lo que falta pagar
            falta = round(total() - pagado(), 2)
            if not monto.get().strip() and falta > 0:
                monto.set(money_to_input(falta))
            entry.focus_set()
            entry.select_range(0, "end")

        box.bind("<<ComboboxSelected>>", sugerir)
        box.bind("<Return>", agregar)
        entry.bind("<Return>", agregar)
        if field.total in self.vars:
            self.vars[field.total].trace_add("write", lambda *_: refresh())
        self.widgets[field.key] = box
        refresh()

    def _toggle(self, field, keep=False):
        """Casilla que anula otro campo: lo deshabilita y lo pone en 0 (salvo `keep`, al abrir)."""
        target = field.disables
        if not target:
            return
        on = self.vars[field.key].get() == "1"
        if on and not keep:
            self.vars[target].set("0")
        self.widgets[target].configure(state="disabled" if on else "normal")

    @staticmethod
    def _initial(field, values):
        if field.kind == "datetime":   # nuevo: la fecha y hora actuales; edición: la guardada
            return fmt_datetime(values[field.key] if values else now_iso())
        if field.kind == "date":   # vacía hasta que se elige
            return fmt_date(values[field.key]) if values else ""
        if not values:
            return field.default or ("0" if field.kind in ("int", "bool") else "")
        v = values[field.key]
        return money_to_input(v) if field.kind == "money" else str(v)

    def _fail(self, message, field=None):
        self.error.config(text=message)
        if field:
            self.widgets[field.key].focus_set()

    def _save(self):
        data = {}
        for f in self.fields:
            if f.kind == "multi":
                data[f.key] = [self.multi_ids[f.key][i] for i in self.multi_boxes[f.key].curselection()]
                continue
            if f.kind == "pagos":
                cuenta, monto = self.pago_vars[f.key]
                if cuenta.get() or monto.get().strip():
                    return self._fail("Pagos: tocá Agregar para registrar el pago que escribiste (o borralo).", f)
                data[f.key] = list(self.pagos[f.key])
                continue
            if f.kind in ("select", "list"):   # listas cerradas: lo escrito tiene que ser una de las opciones
                if self.widgets[f.key].resolver() is None:
                    return self._fail(f"{f.label}: elegí una opción de la lista.", f)
                self.widgets[f.key].confirmar()
            raw = self.vars[f.key].get().strip()
            if f.kind == "bool":
                data[f.key] = int(raw == "1")
                continue
            if f.kind == "select":
                if not raw and f.required:
                    return self._fail(f"{f.label} es obligatorio.", f)
                data[f.key] = self.select_ids[f.key][raw] if raw else None
                continue
            if f.kind == "datetime":
                if self.values and raw == self._initial(f, self.values):
                    data[f.key] = self.values[f.key]   # sin tocar: queda tal cual estaba (con sus segundos)
                    continue
                try:
                    data[f.key] = parse_datetime(raw)
                except ValueError:
                    return self._fail(f"{f.label}: usá el formato dd/mm/aaaa hh:mm.", f)
                continue
            if f.kind == "date":
                if not raw:
                    data[f.key] = ""
                    continue
                try:
                    data[f.key] = parse_date(raw)
                except ValueError:
                    return self._fail(f"{f.label}: usá el formato dd/mm/aaaa.", f)
                continue
            if f.digits:
                raw = re.sub(r"[\s\-()]", "", raw)   # tolera espacios, guiones y paréntesis al pegar
                largos = f.digits if isinstance(f.digits, tuple) else (f.digits,)
                if raw and not (raw.isdigit() and len(raw) in largos):
                    cuantos = " u ".join([", ".join(map(str, largos[:-1])), str(largos[-1])] if len(largos) > 1
                                         else [str(largos[0])])
                    return self._fail(f"{f.label}: tiene que tener {cuantos} dígitos, solo números.", f)
            if f.kind == "email":
                raw = raw.lower()
                if raw and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", raw):
                    return self._fail(f"{f.label}: no parece una dirección válida.", f)
            if f.required and not raw:
                return self._fail(f"{f.label} es obligatorio.", f)
            try:
                if f.kind == "money":
                    data[f.key] = parse_money(raw)
                elif f.kind == "int":
                    data[f.key] = parse_int(raw, f.signed)
                elif f.kind in ("list", "email"):
                    data[f.key] = raw
                else:
                    data[f.key] = raw.upper()
            except ValueError:
                return self._fail(f"{f.label}: ingresá un número válido.", f)
        error = self.on_save(data, self)
        if error:
            return self._fail(error)
        self.destroy()
