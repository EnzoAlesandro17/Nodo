"""Sección Data: descargar cada tabla y cargar cambios en masa con archivos CSV (una lista por tabla)."""
from datetime import date
from tkinter import filedialog, messagebox, ttk

from db import administracion, importer, stock
from ui import backup_ui, theme
from ui.base import Screen
from ui.import_dialog import ImportPreview
from ui.paths import escritorio

# (nombre, repositorio): el CSV de cada tabla solo modifica esa tabla. Se identifican por su clave (repo.clave).
TABLAS = (
    ("Equipos", stock.equipos),
    ("Accesorios", stock.accesorios),
    ("Sucursales", administracion.sucursales),
    ("Empleados", administracion.empleados),
    ("Cuentas", administracion.cuentas),
    ("Planes", administracion.planes),
    ("Planes BAF", administracion.planes_baf),
    ("Descuentos", administracion.descuentos),
)


class Data(Screen):
    title = "Data"
    subtitle = "Copia de seguridad de la base y, por tabla, descarga y carga en masa con archivos CSV"

    def build(self, card):
        card.configure(padding=(24, 16))
        copia = ttk.Frame(card, style="Inner.TFrame")
        copia.pack(fill="x")
        ttk.Label(copia, text="Copia de seguridad", style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(side="left")
        ttk.Button(copia, text="Hacer copia ahora", style="Accent.TButton", command=self._copia).pack(side="left", padx=(16, 0))
        self.lbl_copia = ttk.Label(copia, style="Card.TLabel")
        self.lbl_copia.pack(side="left", padx=14)
        self._texto_copia()
        ttk.Label(card, style="Muted.TLabel", wraplength=1000, justify="left", text=(
            "Toda la base es un solo archivo. La copia sale verificada, donde elijas (te propone el Escritorio), aunque Nodo "
            "esté abierto. Para restaurarla, copiala como nodo.db a la carpeta data con Nodo cerrado.")).pack(anchor="w", pady=(4, 0))
        ttk.Separator(card).pack(fill="x", pady=8)
        ttk.Label(card, text="Descargar y cargar por CSV", style="Card.TLabel", font=("Segoe UI", 12, "bold")).pack(anchor="w")
        ttk.Label(card, style="Muted.TLabel", wraplength=1000, justify="left", text=(
            "Cada tabla tiene su archivo: cargar uno solo modifica esa tabla. Lo que existe se actualiza (se busca por "
            "«Se identifica por»), lo nuevo se agrega, una celda vacía deja el valor como está y el stock no se toca. "
            "Antes de aplicar hay una vista previa. Los archivos se abren con Excel.")).pack(anchor="w", pady=(2, 6))
        grid = ttk.Frame(card, style="Inner.TFrame")
        grid.pack(fill="x")
        grid.columnconfigure(2, weight=1)
        for col, text in enumerate(("Tabla", "Se identifica por", "En esta base")):
            ttk.Label(grid, text=text, style="Muted.TLabel", font=("Segoe UI", 9, "bold")).grid(
                row=0, column=col, sticky="w", padx=(0, 24), pady=(0, 4))
        self.counts = {}
        for r, (nombre, repo) in enumerate(TABLAS, start=1):
            clave = next(f.label for f in repo.fields if f.key == repo.clave)
            ttk.Label(grid, text=nombre, style="Card.TLabel", font=("Segoe UI", 11, "bold")).grid(
                row=r, column=0, sticky="w", padx=(0, 24), pady=1)
            ttk.Label(grid, text=clave, style="Card.TLabel").grid(row=r, column=1, sticky="w", padx=(0, 24))
            self.counts[nombre] = ttk.Label(grid, style="Muted.TLabel")
            self.counts[nombre].grid(row=r, column=2, sticky="w")
            ttk.Button(grid, text="Descargar CSV", padding=(10, 2), command=lambda n=nombre, p=repo: self._descargar(n, p)
                       ).grid(row=r, column=3, padx=(8, 0), pady=1)
            ttk.Button(grid, text="Cargar CSV", padding=(10, 2), command=lambda n=nombre, p=repo: self._cargar(n, p)
                       ).grid(row=r, column=4, padx=(8, 0), pady=1)
        self._counts()

    def build_actions(self, bar):
        """Sin barra de acciones: los botones están en cada tabla."""

    def _texto_copia(self):
        texto, avisar = backup_ui.texto_ultima_copia()
        self.lbl_copia.config(text=texto, foreground=theme.DANGER if avisar else theme.MUTED)

    def _copia(self):
        backup_ui.hacer_copia(self.winfo_toplevel())
        self._texto_copia()

    def _counts(self):
        for nombre, repo in TABLAS:
            n = len(repo.list())
            self.counts[nombre].config(text=f"{n} registro{'' if n == 1 else 's'} activo{'' if n == 1 else 's'}")

    def _descargar(self, nombre, repo):
        top = self.winfo_toplevel()
        path = filedialog.asksaveasfilename(
            parent=top, title=f"Descargar {nombre}: elegí dónde guardarlo", defaultextension=".csv",
            initialdir=escritorio(), initialfile=f"{nombre.lower().replace(' ', '_')}_{date.today().isoformat()}.csv",
            filetypes=[("CSV", "*.csv")])
        if not path:
            return
        try:
            n = importer.export_csv(repo, path)
        except OSError as e:
            return messagebox.showerror("No se pudo descargar", str(e), parent=top)
        messagebox.showinfo("Descarga lista", f"Se descargaron {n} registros de {nombre}.\n\n{path}", parent=top)

    def _cargar(self, nombre, repo):
        top = self.winfo_toplevel()
        path = filedialog.askopenfilename(parent=top, title=f"Cargar {nombre}", initialdir=escritorio(),
                                          filetypes=[("CSV", "*.csv"), ("Todos los archivos", "*.*")])
        if not path:
            return
        try:
            plan = importer.build_plan(repo, path)
        except (importer.CsvError, OSError) as e:
            return messagebox.showerror("No se pudo leer el archivo", str(e), parent=top)
        ImportPreview(top, plan, title=f"Cargar {nombre}",
                      on_apply=lambda force, baja: self._aplicar(nombre, repo, plan, force, baja))

    def _aplicar(self, nombre, repo, plan, force, baja):
        mod, alt, bajas = importer.apply_plan(repo, plan, force, baja)
        self._counts()
        messagebox.showinfo("Carga lista", f"{nombre}: {mod} modificados, {alt} altas y {bajas} bajas.",
                            parent=self.winfo_toplevel())
