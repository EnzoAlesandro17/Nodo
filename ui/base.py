"""Pantalla base: encabezado + tarjeta de contenido + barra de acciones."""
from tkinter import ttk


class Screen(ttk.Frame):
    title = ""
    subtitle = ""
    actions = ("Limpiar", "Guardar")  # el último es el botón principal

    def __init__(self, parent):
        super().__init__(parent, padding=(28, 22))
        ttk.Label(self, text=self.title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text=self.subtitle, style="Sub.TLabel").pack(anchor="w", pady=(2, 16))

        self.card = ttk.Frame(self, style="Card.TFrame", padding=24)
        self.card.pack(fill="both", expand=True)
        self.build(self.card)

        bar = ttk.Frame(self, padding=(0, 14, 0, 0))
        bar.pack(fill="x")
        self.build_actions(bar)

    def build(self, card):
        """Sobrescribir en cada pantalla. Por defecto muestra un placeholder."""
        holder = ttk.Frame(card, style="Inner.TFrame")
        holder.place(relx=0.5, rely=0.5, anchor="center")
        ttk.Label(holder, text=self.title, style="Card.TLabel",
                  font=("Segoe UI", 14, "bold")).pack()
        ttk.Label(holder, text="Formulario pendiente de definir", style="Muted.TLabel").pack(pady=(4, 0))

    def build_actions(self, bar):
        """Barra inferior. Por defecto, botones deshabilitados (pantallas aún sin definir)."""
        for i, text in enumerate(reversed(self.actions)):
            ttk.Button(bar, text=text, state="disabled",
                       style="Accent.TButton" if i == 0 else "TButton").pack(side="right", padx=(8, 0))
