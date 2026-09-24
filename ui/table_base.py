"""Pantalla de tabla genérica: buscador + filtro, tabla y botones Nuevo / Editar / Borrar.

Las pantallas concretas (stock, gestiones) definen el repositorio y los textos, y
completan las partes que cambian: guardado (_save_new / _save_edit) y el aviso de baja.
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ui import theme
from ui.autocomplete import Combobox, normalizar
from ui.base import Screen
from ui.form_dialog import FormDialog
from ui.formatting import fmt_date, fmt_datetime, fmt_int, fmt_money
from ui.period_filter import PeriodFilter


class TableScreen(Screen):
    repo = None                       # db.repo.Repo
    filter_all = "TODOS"              # texto de la opción "sin filtro"
    noun, noun_plural = "registro", "registros"
    form_new, form_edit = "Nuevo registro", "Editar registro"
    default_sort, default_desc = "codigo", False
    left_keys = ("descripcion",)      # columnas alineadas a la izquierda (el resto, centradas)
    form_columns = 1                  # columnas de campos del formulario (más de 1 para los muy largos)
    zebra = True                      # filas alternadas en gris (False si row_tags ya pinta el fondo de cada fila)
    orden_columnas = ()               # claves de las columnas, si el orden no es el de los campos (formularios por secciones)

    def __init__(self, parent):
        self.rows = {}
        self._todas = []   # filas del filtro y el período elegidos, antes de Buscar: [(fila, texto normalizado)]
        self.sort_key, self.sort_desc = self.default_sort, self.default_desc
        super().__init__(parent)
        self.reload()
        self.search_entry.focus_set()

    @property
    def fields(self):
        return self.repo.fields

    @property
    def fecha_key(self):
        """Campo de fecha principal (para el filtro por período), si la tabla tiene uno."""
        return next((f.key for f in self.fields if f.key == "fecha" and f.kind in ("date", "datetime")), None)

    @property
    def columns(self):
        """Campos que se muestran como columnas de la tabla."""
        if self.orden_columnas:
            por_clave = {f.key: f for f in self.fields}
            return [por_clave[k] for k in self.orden_columnas]
        return [f for f in self.fields if f.kind != "bool" and f.in_table]

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        top = ttk.Frame(card, style="Inner.TFrame")
        top.pack(fill="x", pady=(0, 12))

        # Un solo renglón: Buscar (en tiempo real, en cualquier dato), el filtro de la tabla y, a la derecha, el período
        ttk.Label(top, text="Buscar", style="Card.TLabel").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(top, textvariable=self.search_var, width=20)
        self.search_entry.pack(side="left", padx=(8, 14))
        self.search_var.trace_add("write", lambda *_: self._buscar())

        filter_field = next(f for f in self.fields if f.key == self.repo.filter_key)
        ttk.Label(top, text=filter_field.label, style="Card.TLabel").pack(side="left")
        self.filter_var = tk.StringVar(value=self.filter_all)
        self.filter_box = Combobox(top, textvariable=self.filter_var, state="readonly", width=14)
        self.filter_box.pack(side="left", padx=(8, 10))
        self.filter_box.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        ttk.Button(top, text="Limpiar", command=self._clear_filters).pack(side="left")

        if self.fecha_key:
            self.periodo = PeriodFilter(top, self.refresh)
            self.periodo.frame.pack(side="right")

        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, columns=[f.key for f in self.columns], show="headings",
                                 selectmode="browse")
        for f in self.columns:
            anchor = "w" if f.key in self.left_keys else "center"
            self.tree.heading(f.key, text=f.titulo, anchor=anchor, command=lambda k=f.key: self._sort(k))
            self.tree.column(f.key, width=f.width, minwidth=60, stretch=f.stretch, anchor=anchor)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.tag_configure("viejo", foreground=theme.DANGER)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._update_buttons())
        self.tree.bind("<Double-1>", self._on_double_click)
        self._update_headings()

    def build_actions(self, bar):
        self.btn_new = ttk.Button(bar, text="Nuevo", style="Accent.TButton", command=self.new)
        self.btn_edit = ttk.Button(bar, text="Editar", command=self.edit)
        self.btn_del = ttk.Button(bar, text="Borrar", style="Danger.TButton", command=self.delete)
        for b in (self.btn_new, self.btn_edit, self.btn_del):
            b.pack(side="left", padx=(0, 8))
        self.extra_actions(bar)
        self.count = ttk.Label(bar, style="Sub.TLabel")
        self.count.pack(side="right")
        self._update_buttons()

    def extra_actions(self, bar):
        """Botones adicionales a la derecha de Borrar (opcional)."""

    # --- datos ---------------------------------------------------------
    def reload(self, select=None):
        """Refresca las opciones del filtro y la tabla (tras alta/edición/baja)."""
        values = [self.filter_all] + self.repo.distinct(self.repo.filter_key)
        self.filter_box.configure(values=values)
        if self.filter_var.get() not in values:
            self.filter_var.set(self.filter_all)
        self.refresh(select)

    def refresh(self, select=None):
        """Vuelve a leer las filas del filtro y el período elegidos, y aplica Buscar."""
        if not self.filter_var.get():   # filtro vaciado (se escribió algo que no es una opción): vuelve a TODOS
            self.filter_var.set(self.filter_all)
        fv = self.filter_var.get()
        rows = self.repo.list("", None if fv == self.filter_all else fv)
        if self.fecha_key:
            desde, hasta = self.periodo.rango()
            if desde:
                rows = [r for r in rows if r[self.fecha_key][:10] >= desde]
            if hasta:
                rows = [r for r in rows if r[self.fecha_key][:10] <= hasta]
        self._todas = [(r, self._texto_busqueda(r)) for r in rows]
        self._buscar(select)

    def _texto_busqueda(self, row):
        """Todo lo que se puede buscar de una fila: cada campo tal como se ve (también los que no son columna)."""
        partes = []
        for f in self.fields:
            if f.kind in ("bool", "pagos") or f.key not in row:
                continue
            partes.append(str(self._display(f, row)))
            if f.kind in ("money", "int"):   # los números también sin separador de miles: 1500 = 1.500
                partes.append(str(row[f.key]))
        return normalizar(" ".join(partes))

    def _buscar(self, select=None):
        """Muestra las filas que tienen todas las palabras de Buscar (sin importar mayúsculas ni acentos)."""
        palabras = normalizar(self.search_var.get()).split()
        rows = [r for r, texto in self._todas if all(p in texto for p in palabras)]
        rows.sort(key=lambda r: self.sort_value(r, self.sort_key), reverse=self.sort_desc)

        keep = select if select is not None else self._selected_id()
        self.rows = {r["id"]: r for r in rows}
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(rows):
            self.tree.insert("", "end", iid=str(r["id"]), tags=(("odd",) if i % 2 and self.zebra else ()) + self.row_tags(r),
                             values=[self._display(f, r) for f in self.columns])
        if keep in self.rows:
            self.tree.selection_set(str(keep))
            self.tree.see(str(keep))
        n = len(rows)
        self.count.config(text=f"{n} {self.noun if n == 1 else self.noun_plural}")
        self._update_buttons()

    def row_tags(self, row):
        """Etiquetas extra de la fila (p. ej. "viejo" la pinta en rojo)."""
        return ()

    def sort_value(self, row, key):
        return row.get(key + "_label", row[key])   # select / multi: se ordena por el texto mostrado

    def _display(self, field, row):
        value = row[field.key]
        if field.kind == "money":
            return fmt_money(value)
        if field.kind == "int":
            return fmt_int(value)
        if field.kind == "datetime":
            return fmt_datetime(value)
        if field.kind == "date":
            return fmt_date(value)
        if field.kind in ("select", "multi"):
            return row.get(field.key + "_label") or ""
        return value

    def _sort(self, key):
        self.sort_desc = not self.sort_desc if key == self.sort_key else False
        self.sort_key = key
        self._update_headings()
        self._buscar()

    def _update_headings(self):
        arrow = " ▼" if self.sort_desc else " ▲"
        for f in self.columns:
            self.tree.heading(f.key, text=f.titulo + (arrow if f.key == self.sort_key else ""))

    def _clear_filters(self):
        self.search_var.set("")
        self.filter_var.set(self.filter_all)
        if self.fecha_key:
            self.periodo.reset()
        self.refresh()
        self.search_entry.focus_set()

    # --- selección -----------------------------------------------------
    def _selected_id(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    def _update_buttons(self):
        state = "normal" if self._selected_id() is not None else "disabled"
        self.btn_edit.config(state=state)
        self.btn_del.config(state=state)

    def _on_double_click(self, event):
        if self.tree.identify_row(event.y):
            self.edit()

    # --- acciones ------------------------------------------------------
    def _choices(self):
        return {f.key: list(dict.fromkeys(list(f.options) + self.repo.distinct(f.key)))   # las sugeridas y las ya cargadas
                for f in self.fields if f.kind == "choice"}

    def _defaults(self):
        """Valores iniciales de los campos select en un alta ({campo: id}). Por defecto, ninguno."""
        return {}

    def _suggestions(self):
        """Campos select que proponen un precio: {campo: (campo destino, {id: precio})}."""
        return {}

    def new(self):
        FormDialog(self.winfo_toplevel(), self.form_new, self.fields, choices=self._choices(),
                   on_save=self._save_new, defaults=self._defaults(), suggestions=self._suggestions(),
                   columns=self.form_columns)

    def edit(self):
        row_id = self._selected_id()
        if row_id is None:
            return
        FormDialog(self.winfo_toplevel(), self.form_edit, self.fields, values=self.rows[row_id],
                   choices=self._choices(), on_save=lambda data, dlg: self._save_edit(row_id, data),
                   suggestions=self._suggestions(), columns=self.form_columns)

    def _save_new(self, data, dialog):
        """Guarda un alta. Devuelve un mensaje de error o None."""
        raise NotImplementedError

    def _save_edit(self, row_id, data):
        """Guarda una edición. Devuelve un mensaje de error o None."""
        raise NotImplementedError

    def delete_prompt(self, row):
        """(título, mensaje) de la confirmación de baja."""
        raise NotImplementedError

    def delete(self):
        row_id = self._selected_id()
        if row_id is None:
            return
        title, message = self.delete_prompt(self.rows[row_id])
        if messagebox.askyesno(title, message, icon="warning", parent=self.winfo_toplevel()):
            self.repo.deactivate(row_id)
            self.reload()
