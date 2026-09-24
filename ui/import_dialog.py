"""Vista previa de una importación CSV: qué se modifica, qué se agrega y qué se omite."""
import tkinter as tk
from tkinter import ttk

from ui import theme
from ui.base import arriba


class ImportPreview(tk.Toplevel):
    """`on_apply(include_conflicts, deactivate_missing)` escribe los cambios; la ventana se cierra después."""

    def __init__(self, parent, plan, on_apply, title="Importar"):
        super().__init__(parent, bg=theme.BG)
        self.title(title)
        self.transient(parent)
        self.geometry("900x520")
        self.minsize(700, 400)
        self.plan, self.on_apply = plan, on_apply

        head = ttk.Frame(self, padding=(24, 18, 24, 8))
        head.pack(fill="x")
        ttk.Label(head, text="Vista previa de la importación", style="Title.TLabel",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(head, text=self._summary(), style="Sub.TLabel", wraplength=850).pack(anchor="w", pady=(2, 0))

        notes = self._notes()
        if notes:
            ttk.Label(head, text=notes, style="Sub.TLabel", wraplength=850).pack(anchor="w", pady=(2, 0))

        book = ttk.Notebook(self)
        book.pack(fill="both", expand=True, padx=24, pady=(4, 0))
        clave, nombre = plan.clave_label, plan.nombre_label
        self._tab(book, f"Modificados ({len(plan.updates)})", (clave, nombre, "Cambios"),
                  [(u["clave"], u["nombre"], self._changes(u)) for u in plan.updates])
        self._tab(book, f"Altas ({len(plan.inserts)})", (clave, nombre, "Datos"),
                  [(i["clave"], i["nombre"], i["resumen"]) for i in plan.inserts])
        if plan.conflicts:
            self._tab(book, f"Conflictos ({len(plan.conflicts)})", (clave, f"{nombre} actual", "Cambios (no se aplican)"),
                      [(c["clave"], c["nombre"], self._changes(c)) for c in plan.conflicts])
        self._tab(book, f"No están en el archivo ({len(plan.missing)})", (clave, nombre, ""),
                  [(m["clave"], m["nombre"], "") for m in plan.missing])
        self._tab(book, f"Omitidos ({len(plan.skipped)})", (clave, "Fila del archivo", "Motivo"),
                  [(code, line, why) for line, code, why in plan.skipped])

        bar = ttk.Frame(self, padding=(24, 12, 24, 18))
        bar.pack(fill="x")
        self.force, self.baja = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
        checks = ttk.Frame(bar)
        checks.pack(side="left")
        if plan.conflicts:
            ttk.Checkbutton(checks, text="Aplicar también los conflictos", variable=self.force,
                            command=self._update_apply).pack(anchor="w")
        if plan.missing:
            ttk.Checkbutton(checks, text=f"Dar de baja los {len(plan.missing)} que no están en el archivo",
                            variable=self.baja, command=self._update_apply).pack(anchor="w")
        self.btn_apply = ttk.Button(bar, text="Aplicar", style="Accent.TButton", command=self._apply)
        self.btn_apply.pack(side="right")
        ttk.Button(bar, text="Cancelar", command=self.destroy).pack(side="right", padx=(0, 8))
        self._update_apply()

        self.bind("<Escape>", lambda e: self.destroy())
        arriba(self, parent)
        self.wait_visibility()
        self.grab_set()

    # --- textos --------------------------------------------------------
    def _summary(self):
        p = self.plan
        text = (f"{len(p.updates)} a modificar · {len(p.inserts)} altas · {len(p.conflicts)} conflictos · "
                f"{p.unchanged} sin cambios · {len(p.skipped)} omitidos · {len(p.missing)} no están en el archivo. ")
        text += "Lo que no está en el archivo no se toca, salvo que marques darlo de baja."
        if p.tiene_stock:
            text += " El stock no se modifica."
        return text

    def _notes(self):
        p = self.plan
        notes = []
        if p.ignored:
            notes.append("Columnas ignoradas: " + ", ".join(p.ignored) + ".")
        if p.tiene_descripcion and not any(f.key == "descripcion" for f in p.columns):
            notes.append("El archivo no trae descripción: no se pudo validar que coincida con el código.")
        return " ".join(notes)

    @staticmethod
    def _changes(entry):
        return " · ".join(f"{label}: {old} → {new}" for label, (old, new) in entry["changes"].items())

    # --- widgets -------------------------------------------------------
    def _tab(self, book, title, headings, rows):
        frame = ttk.Frame(book, style="Inner.TFrame", padding=8)
        book.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=("a", "b", "c"), show="headings", selectmode="browse")
        for col, text, width, stretch in zip("abc", headings, (130, 260, 440), (False, False, True)):
            tree.heading(col, text=text, anchor="w")
            tree.column(col, width=width, minwidth=80, stretch=stretch, anchor="w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        for i, row in enumerate(rows):
            tree.insert("", "end", values=row, tags=("odd",) if i % 2 else ())
        tree.tag_configure("odd", background=theme.ZEBRA)

    def _update_apply(self):
        n = len(self.plan.updates) + len(self.plan.inserts)
        if self.force.get():
            n += len(self.plan.conflicts)
        if self.baja.get():
            n += len(self.plan.missing)
        self.btn_apply.config(text=f"Aplicar ({n})", state="normal" if n else "disabled")

    def _apply(self):
        self.on_apply(self.force.get(), self.baja.get())
        self.destroy()
