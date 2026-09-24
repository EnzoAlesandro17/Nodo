"""Caja > Arqueo de caja (traído de MyTools): caja fuerte + caja chica contra el saldo del sistema."""
import tkinter as tk
from datetime import date, datetime
from tkinter import filedialog, messagebox, ttk

from db import administracion, arqueos
from ui import entry_helpers, theme
from ui.autocomplete import Combobox, normalizar
from ui.base import Screen, arriba
from ui.formatting import fmt_datetime, fmt_money
from ui.paths import escritorio
from ui.period_filter import PeriodFilter

TODOS = "TODOS"


class Arqueo(Screen):
    title = "Caja · Arqueo de caja"
    subtitle = "Lo que hay en la caja fuerte y en la chica contra el saldo del sistema; la diferencia se arrastra al siguiente"

    def __init__(self, parent):
        self.rows, self.visibles = [], {}
        super().__init__(parent)
        self.refresh()

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        top = ttk.Frame(card, style="Inner.TFrame")
        top.pack(fill="x")
        self.buscar, self.empleado = tk.StringVar(), tk.StringVar(value=TODOS)
        ttk.Label(top, text="Buscar", style="Card.TLabel").pack(side="left")
        entry = ttk.Entry(top, textvariable=self.buscar, width=20)
        entry.pack(side="left", padx=(6, 18))
        self.buscar.trace_add("write", lambda *_: self._mostrar())
        ttk.Label(top, text="Empleado", style="Card.TLabel").pack(side="left")
        self.cmb_empleado = Combobox(top, textvariable=self.empleado, state="readonly", width=16)
        self.cmb_empleado.pack(side="left", padx=6)
        self.cmb_empleado.bind("<<ComboboxSelected>>", lambda e: self._mostrar())
        self.periodo = PeriodFilter(top, self.refresh, modo_inicial="Mes")
        self.periodo.frame.pack(side="right")

        self.stats = ttk.Label(card, style="Muted.TLabel")
        self.stats.pack(anchor="w", pady=(10, 8))

        columnas = (("fecha", "Fecha y hora", 130, "center"), ("empleados", "Empleados", 200, "w"),
                    ("cf", "Caja fuerte", 115, "e"), ("cc", "Caja chica", 115, "e"), ("sc", "Saldo sistema", 120, "e"),
                    ("variacion", "Variación", 150, "center"), ("resultado", "Resultado acumulado", 160, "center"))
        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in columnas], show="headings", selectmode="browse")
        for key, texto, ancho, anchor in columnas:
            self.tree.heading(key, text=texto, anchor=anchor)
            self.tree.column(key, width=ancho, minwidth=60, stretch=key == "empleados", anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.tag_configure("falta", foreground=theme.DANGER)
        self.tree.tag_configure("sobra", foreground=theme.OK)
        self.tree.bind("<Double-1>", lambda e: self._detalle() if self.tree.identify_row(e.y) else None)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._botones())
        self.vacio = ttk.Label(wrap, text="No hay arqueos en este período.\nUsá «Nuevo arqueo» o cambiá el Año, el Mes o las fechas.",
                               style="Muted.TLabel", justify="center")

    def build_actions(self, bar):
        ttk.Button(bar, text="Nuevo arqueo", style="Accent.TButton", command=self._nuevo).pack(side="left")
        self.btn_detalle = ttk.Button(bar, text="Ver detalle", command=self._detalle)
        self.btn_detalle.pack(side="left", padx=8)
        ttk.Button(bar, text="Exportar Excel", command=self._exportar).pack(side="left")
        self.count = ttk.Label(bar, style="Sub.TLabel")
        self.count.pack(side="right")
        self._botones()

    # --- datos ---------------------------------------------------------
    def _en_periodo(self, r):
        desde, hasta = self.periodo.rango()
        return (not desde or r["fecha"][:10] >= desde) and (not hasta or r["fecha"][:10] <= hasta)

    def refresh(self):
        self.rows = arqueos.listar()   # el resultado se arrastra: hacen falta todos, aunque se muestre un período
        for r in self.rows:   # Buscar encuentra cualquier dato de la fila, tal como se ve
            r["_texto"] = normalizar(" ".join([fmt_datetime(r["fecha"]), ", ".join(r["empleados"])] + [
                fmt_money(r[k]) for k in ("cf_val", "cc_val", "sc_val")] + [
                arqueos.etiqueta(r["variacion"]), arqueos.etiqueta(r["resultado"])]))
        nombres = sorted({n for r in self.rows if self._en_periodo(r) for n in r["empleados"]})
        self.cmb_empleado.configure(values=[TODOS] + nombres)
        if self.empleado.get() not in [TODOS] + nombres:
            self.empleado.set(TODOS)
        self._mostrar()

    def _mostrar(self):
        palabras = normalizar(self.buscar.get()).split()
        emp = self.empleado.get()
        todas_del_mes = [r for r in self.rows if self._en_periodo(r)]
        rows = [r for r in todas_del_mes
                if (emp in ("", TODOS) or emp in r["empleados"]) and all(p in r["_texto"] for p in palabras)]
        self.visibles = {str(r["id"]): r for r in rows}
        self.tree.delete(*self.tree.get_children())
        for n, r in enumerate(rows):
            v = r["variacion"]
            tags = (("odd",) if n % 2 else ()) + (("sobra",) if v > arqueos.EPS else ("falta",) if v < -arqueos.EPS else ())
            self.tree.insert("", "end", iid=str(r["id"]), tags=tags, values=(
                fmt_datetime(r["fecha"]), ", ".join(r["empleados"]) or "—", fmt_money(r["cf_val"]), fmt_money(r["cc_val"]),
                fmt_money(r["sc_val"]), arqueos.etiqueta(v), arqueos.etiqueta(r["resultado"])))
        if rows:
            self.vacio.place_forget()
        else:
            self.vacio.place(relx=0.5, rely=0.4, anchor="center")
        faltan = sum(1 for r in todas_del_mes if r["variacion"] < -arqueos.EPS)
        sobran = sum(1 for r in todas_del_mes if r["variacion"] > arqueos.EPS)
        ultimo = self.rows[0] if self.rows else None
        self.stats.config(text=f"{len(todas_del_mes)} arqueos del período  ·  {faltan} con faltante  ·  {sobran} con sobrante  ·  "
                               f"{len(todas_del_mes) - faltan - sobran} bien  ·  Resultado actual: "
                               + (arqueos.etiqueta(ultimo["resultado"]) if ultimo else "—"))
        self.count.config(text=f"{len(rows)} arqueo{'' if len(rows) == 1 else 's'}")
        self._botones()

    def _botones(self):
        if hasattr(self, "btn_detalle"):
            self.btn_detalle.config(state="normal" if self.tree.selection() else "disabled")

    # --- acciones ------------------------------------------------------
    def _nuevo(self):
        NuevoArqueo(self.winfo_toplevel(), on_saved=self._guardado)

    def _guardado(self):
        self.periodo.reset()   # vuelve al mes actual, donde está el arqueo nuevo
        self.refresh()
        if self.tree.get_children():
            self.tree.selection_set(self.tree.get_children()[0])

    def _detalle(self):
        sel = self.tree.selection()
        if not sel:
            return
        r = self.visibles[sel[0]]
        messagebox.showinfo("Arqueo", "\n".join([
            f"{fmt_datetime(r['fecha'])}  ·  {', '.join(r['empleados']) or '—'}", "",
            f"Caja fuerte:    {fmt_money(r['cf_val'])}    ({r['cf_expr']})",
            f"Caja chica:      {fmt_money(r['cc_val'])}    ({r['cc_expr']})",
            f"Saldo sistema: {fmt_money(r['sc_val'])}    ({r['sc_expr']})", "",
            f"Variación:  {arqueos.etiqueta(r['variacion'])}", f"Resultado acumulado:  {arqueos.etiqueta(r['resultado'])}"]),
            parent=self.winfo_toplevel())

    def _exportar(self):
        top = self.winfo_toplevel()
        path = filedialog.asksaveasfilename(
            parent=top, title="Exportar arqueos: elegí dónde guardarlos", defaultextension=".xlsx",
            initialdir=escritorio(), initialfile=f"arqueo_{date.today().isoformat()}.xlsx", filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            n = arqueos.exportar_xlsx(path)
        except (OSError, ImportError) as e:
            return messagebox.showerror("No se pudo exportar", str(e), parent=top)
        messagebox.showinfo("Exportar", f"Se exportaron {n} arqueos.\n\n{path}", parent=top)


class NuevoArqueo(tk.Toplevel):
    """Formulario de un arqueo: empleados, los tres montos (se pueden escribir como suma) y el resultado en vivo."""

    def __init__(self, parent, on_saved):
        super().__init__(parent, bg=theme.BG)
        self.title("Nuevo arqueo")
        self.transient(parent)
        self.resizable(False, False)
        self.on_saved = on_saved
        self.previo = arqueos.anterior()   # el arqueo anterior: de ahí sale la caja fuerte precargada y lo que se arrastra
        body = ttk.Frame(self, padding=(28, 22, 28, 4))
        body.pack(fill="both")
        ttk.Label(body, text="Nuevo arqueo", style="Title.TLabel", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))

        ttk.Label(body, text="Empleados").grid(row=1, column=0, sticky="nw", padx=(0, 18), pady=6)
        holder = ttk.Frame(body)
        holder.grid(row=1, column=1, sticky="w")
        self.nombres = [e["nombre"] for e in administracion.empleados.list()]
        self.lista = tk.Listbox(holder, selectmode="multiple", exportselection=False, activestyle="none", bd=1, relief="solid",
                                highlightthickness=0, height=6, width=34, font=theme.FONT, selectbackground=theme.ACCENT,
                                selectforeground="white")
        for n in self.nombres:
            self.lista.insert("end", n)
        self.lista.pack(side="left")
        barra = ttk.Scrollbar(holder, orient="vertical", command=self.lista.yview)
        self.lista.configure(yscrollcommand=barra.set)
        barra.pack(side="left", fill="y")
        ttk.Label(body, text="Tocá los que hicieron el arqueo (se pueden elegir varios).", style="Sub.TLabel").grid(
            row=2, column=1, sticky="w")

        self.vars = {k: tk.StringVar() for k in ("cf", "cc", "sc")}
        self.vars["cf"].set(self.previo["cf_expr"] if self.previo else "0")
        self.inicial = self.vars["cf"].get()
        for fila, (clave, rotulo, ejemplo) in enumerate((
                ("cf", "Caja fuerte (CF)", "Ej: 700.000  o  +100.000+100.000"),
                ("cc", "Caja chica (CC)", "Ej: +100.000+50.000+2.000+1.111"),
                ("sc", "Saldo sistema (SS)", "Ej: 307.221,43")), start=3):
            ttk.Label(body, text=rotulo).grid(row=fila * 2 - 3, column=0, sticky="w", padx=(0, 18), pady=(10, 0))
            entry = ttk.Entry(body, textvariable=self.vars[clave], width=36)
            entry.grid(row=fila * 2 - 3, column=1, sticky="w", pady=(10, 0))
            ttk.Label(body, text=ejemplo, style="Sub.TLabel").grid(row=fila * 2 - 2, column=1, sticky="w")
            entry_helpers.Undo(entry, self.vars[clave])
            self.vars[clave].trace_add("write", lambda *_: self._vista_previa())
            if clave == "cf":
                self.entry_cf = entry
        if self.previo:
            pista = (f"La caja fuerte se precargó con la del arqueo anterior ({fmt_datetime(self.previo['fecha'])}); "
                     f"su resultado fue «{arqueos.etiqueta(self.previo['resultado'])}» y queda arrastrado.")
        else:
            pista = "No hay arqueos anteriores todavía: arranca en 0."
        ttk.Label(body, text=pista, style="Sub.TLabel", wraplength=430, justify="left").grid(row=9, column=0, columnspan=2,
                                                                                            sticky="w", pady=(10, 0))
        self.lbl_variacion = ttk.Label(body, font=("Segoe UI", 13, "bold"))
        self.lbl_variacion.grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.lbl_resultado = ttk.Label(body, style="Sub.TLabel")
        self.lbl_resultado.grid(row=11, column=0, columnspan=2, sticky="w")
        self.error = ttk.Label(body, text="", foreground=theme.DANGER, wraplength=430)
        self.error.grid(row=12, column=0, columnspan=2, sticky="w", pady=(8, 0))

        barra_botones = ttk.Frame(self, padding=(28, 8, 28, 22))
        barra_botones.pack(fill="x")
        ttk.Button(barra_botones, text="Guardar", style="Accent.TButton", command=self._guardar).pack(side="right")
        ttk.Button(barra_botones, text="Cancelar", command=self._cancelar).pack(side="right", padx=(0, 8))
        self.bind("<Escape>", lambda e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)
        self._vista_previa()
        arriba(self, parent)
        self.wait_visibility()
        self.grab_set()
        self.lista.focus_set()

    def _valores(self):
        cf, cc, sc = (arqueos.evaluar(self.vars[k].get()) for k in ("cf", "cc", "sc"))
        return cf, cc, sc, round(cf + cc - sc, 2)

    def _vista_previa(self):
        _, _, _, resultado = self._valores()
        variacion = round(resultado - (self.previo["resultado"] if self.previo else 0.0), 2)
        self.lbl_variacion.config(text=f"Variación:  {arqueos.etiqueta(variacion)}",
                                  foreground=theme.OK if variacion > arqueos.EPS else theme.DANGER if variacion < -arqueos.EPS else theme.TEXT)
        self.lbl_resultado.config(text=f"Resultado acumulado:  {arqueos.etiqueta(resultado)}")

    def _cambiado(self):
        return bool(self.lista.curselection()) or self.vars["cc"].get().strip() or self.vars["sc"].get().strip() \
            or self.vars["cf"].get() != self.inicial

    def _cancelar(self):
        if self._cambiado() and not messagebox.askyesno("Cerrar", "¿Querés cerrar? Se pierde lo que cargaste.", parent=self):
            return
        self.destroy()

    def _guardar(self):
        elegidos = [self.nombres[i] for i in self.lista.curselection()]
        try:
            arqueos.registrar(elegidos, self.vars["cf"].get(), self.vars["cc"].get(), self.vars["sc"].get())
        except ValueError as e:
            self.error.config(text=str(e))
            return
        self.destroy()
        self.on_saved()
