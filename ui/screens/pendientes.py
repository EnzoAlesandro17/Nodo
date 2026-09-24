"""Data > Datos por completar: lo que quedó cargado a medias o con un dato dudoso, para ir corrigiéndolo."""
from tkinter import ttk

from db import pendientes
from ui import theme
from ui.base import Screen
from ui.formatting import fmt_datetime
from ui.screens import administracion, gestiones, stock

# categoría -> pantalla donde se corrige (se abre con el registro elegido y su formulario de edición)
PANTALLAS = {"regular": gestiones.Regular, "porta": gestiones.Porta, "casim": gestiones.CaSIM,
             "cater": gestiones.CaTER, "sucursales": administracion.Sucursales,
             "empleados": administracion.Empleados, "stock": stock.StockAccesorios,
             "equipos": stock.StockEquipos}


class Pendientes(Screen):
    title = "Data · Datos por completar"
    subtitle = "Registros cargados a medias o con un dato dudoso: elegí uno y doble clic para corregirlo"

    def __init__(self, parent):
        self.categorias = []
        super().__init__(parent)
        self.refresh()

    # --- construcción --------------------------------------------------
    def build(self, card):
        card.configure(padding=16)
        cuerpo = ttk.Frame(card, style="Inner.TFrame")
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(1, weight=1)
        cuerpo.rowconfigure(0, weight=1)
        izquierda = ttk.Frame(cuerpo, style="Inner.TFrame")
        izquierda.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        ttk.Label(izquierda, text="Qué revisar", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w", pady=(0, 6))
        self.lista = ttk.Treeview(izquierda, columns=("titulo", "n"), show="", selectmode="browse", height=8)
        self.lista.column("titulo", width=250, anchor="w")
        self.lista.column("n", width=60, anchor="e")
        self.lista.pack(fill="y", expand=True)
        self.lista.tag_configure("vacia", foreground=theme.MUTED)
        self.lista.bind("<<TreeviewSelect>>", lambda e: self._elegir())

        derecha = ttk.Frame(cuerpo, style="Inner.TFrame")
        derecha.grid(row=0, column=1, sticky="nsew")
        self.titulo = ttk.Label(derecha, style="Card.TLabel", font=theme.FONT_BOLD)
        self.titulo.pack(anchor="w", pady=(0, 6))
        wrap = ttk.Frame(derecha, style="Inner.TFrame")
        wrap.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(wrap, show="headings", selectmode="browse")
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("odd", background=theme.ZEBRA)
        self.tree.bind("<Double-1>", lambda e: self._abrir() if self.tree.identify_row(e.y) else None)
        self.tree.bind("<Return>", lambda e: self._abrir())
        self.vacio = ttk.Label(wrap, text="", style="Muted.TLabel", justify="center")

    def build_actions(self, bar):
        ttk.Button(bar, text="Actualizar", command=self.refresh).pack(side="left")
        self.btn_abrir = ttk.Button(bar, text="Corregir el elegido", style="Accent.TButton", command=self._abrir)
        self.btn_abrir.pack(side="left", padx=8)
        self.total = ttk.Label(bar, style="Sub.TLabel")
        self.total.pack(side="right")

    # --- datos ---------------------------------------------------------
    def refresh(self):
        actual = self.lista.selection()
        self.categorias = {c["clave"]: c for c in pendientes.categorias()}
        self.lista.delete(*self.lista.get_children())
        for clave, c in self.categorias.items():
            self.lista.insert("", "end", iid=clave, tags=(() if c["filas"] else ("vacia",)),
                              values=(c["titulo"], len(c["filas"]) or "✓"))
        pendiente = sum(len(c["filas"]) for k, c in self.categorias.items() if k != "equipos")
        self.total.config(text=f"{pendiente} registros por completar" if pendiente else "Todo al día")
        elegir = actual[0] if actual and actual[0] in self.categorias else next(
            (k for k, c in self.categorias.items() if c["filas"]), next(iter(self.categorias)))
        self.lista.selection_set(elegir)
        self._elegir()

    def _elegir(self):
        sel = self.lista.selection()
        if not sel:
            return
        c = self.categorias[sel[0]]
        self.titulo.config(text=f"{c['titulo']}  ·  {len(c['filas'])}")
        claves = [k for k, _, _ in c["columnas"]]
        self.tree.configure(columns=claves)
        for clave, texto, ancho in c["columnas"]:
            self.tree.heading(clave, text=texto, anchor="w")
            self.tree.column(clave, width=ancho, minwidth=50, anchor="w", stretch=clave in ("falta", "descripcion"))
        self.tree.delete(*self.tree.get_children())
        for n, f in enumerate(c["filas"]):
            self.tree.insert("", "end", iid=str(f["id"]), tags=("odd",) if n % 2 else (), values=[
                fmt_datetime(f[k]) if k == "fecha" else f[k] for k in claves])
        if c["filas"]:
            self.vacio.place_forget()
        else:
            self.vacio.config(text="Nada pendiente en esta lista.")
            self.vacio.place(relx=0.5, rely=0.35, anchor="center")
        self.btn_abrir.config(state="normal" if c["filas"] else "disabled")

    # --- acciones ------------------------------------------------------
    def _abrir(self):
        """Abre la pantalla del registro elegido y su formulario de edición."""
        cat, fila = self.lista.selection(), self.tree.selection()
        if not cat or not fila:
            return
        app = self.winfo_toplevel()
        app.show(PANTALLAS[cat[0]])
        pantalla = app.current
        pantalla.tree.selection_set(fila[0])
        pantalla.tree.see(fila[0])
        pantalla.edit()
