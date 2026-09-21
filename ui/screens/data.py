"""Sección Data: descargar cada tabla y cargar cambios en masa con archivos CSV (una lista por tabla)."""
from datetime import date
from tkinter import filedialog, messagebox, ttk

from db import administracion, importer, stock
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
    subtitle = "Descargá cada tabla y cargá cambios en masa con archivos CSV"

    def build(self, card):
        card.configure(padding=24)
        ttk.Label(card, style="Muted.TLabel", wraplength=900, justify="left", text=(
            "Cada tabla tiene su propio archivo: cargar uno solo modifica esa tabla (subir la lista de sucursales no toca "
            "los equipos). Al cargar, lo que ya existe se actualiza (se busca por el código o nombre de la columna "
            "«Se identifica por») y lo nuevo se agrega; una celda vacía deja el valor como está y el stock nunca se toca. "
            "Antes de aplicar se muestra una vista previa, y se puede dar de baja lo que no esté en el archivo. "
            "Los archivos se abren con Excel.")).pack(anchor="w", pady=(0, 14))
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
                row=r, column=0, sticky="w", padx=(0, 24), pady=5)
            ttk.Label(grid, text=clave, style="Card.TLabel").grid(row=r, column=1, sticky="w", padx=(0, 24))
            self.counts[nombre] = ttk.Label(grid, style="Muted.TLabel")
            self.counts[nombre].grid(row=r, column=2, sticky="w")
            ttk.Button(grid, text="Descargar CSV", command=lambda n=nombre, p=repo: self._descargar(n, p)
                       ).grid(row=r, column=3, padx=(8, 0), pady=3)
            ttk.Button(grid, text="Cargar CSV", command=lambda n=nombre, p=repo: self._cargar(n, p)
                       ).grid(row=r, column=4, padx=(8, 0), pady=3)
        self._counts()

    def build_actions(self, bar):
        """Sin barra de acciones: los botones están en cada tabla."""

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
