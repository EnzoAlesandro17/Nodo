"""Colores, fuentes y estilos ttk compartidos por toda la app.

La paleta sale del design-system (proyectos/design-system, modo claro). Verde y rojo quedan más oscuros que los
de la paleta porque acá se usan como color de texto (sobra/falta) y los de la paleta se leen mal sobre blanco.
"""
from pathlib import Path
import tkinter as tk
from tkinter import ttk

BG = "#F0F0F0"          # fondo general (fondo secundario de la paleta)
SURFACE = "#FFFFFF"     # tarjetas
BAR = "#323332"         # barra superior (texto principal de la paleta)
BAR_HOVER = "#4A4B4A"
BAR_FG = "#F9FAFB"
ACCENT = "#2E5FC7"      # primario
ACCENT_HOVER = "#244FA8"
ACCENT_SOFT = "#E6F0FF"  # fondo sutil / hover
TEXT = "#323332"
MUTED = "#6B7280"
BORDER = "#CBD1D9"
DANGER = "#dc2626"
OK = "#15803d"          # verde: sobra, bien
ZEBRA = "#F7F8FA"
FILA_OK = "#dcfce7"      # fondos de fila por estado: verde (hecho), rojo (cancelado), amarillo (en curso)
FILA_MAL = "#fee2e2"
FILA_PENDIENTE = "#fef9c3"

ICONOS = Path(__file__).resolve().parent.parent / "assets"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUB = ("Segoe UI", 10)
FONT_BAR = ("Segoe UI", 11)


def poner_icono(root):
    """El monograma del design-system como ícono de la ventana y de la barra de tareas."""
    try:
        imgs = [tk.PhotoImage(master=root, file=ICONOS / f"icono-{s}.png") for s in (256, 48, 32, 16)]
    except (tk.TclError, OSError):
        return   # sin los PNG la app arranca igual, con el ícono de Tk
    root.iconphoto(True, *imgs)
    root._iconos = imgs   # que no los libere el recolector


def apply(root):
    root.configure(bg=BG)
    poner_icono(root)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", font=FONT, background=BG, foreground=TEXT)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE, relief="solid", borderwidth=1,
                    bordercolor=BORDER)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Card.TLabel", background=SURFACE)
    style.configure("Title.TLabel", font=FONT_TITLE)
    style.configure("Sub.TLabel", font=FONT_SUB, foreground=MUTED)
    style.configure("Muted.TLabel", background=SURFACE, foreground=MUTED)

    style.configure("TButton", padding=(14, 7), background=SURFACE, bordercolor=BORDER)
    style.map("TButton", background=[("active", ACCENT_SOFT)])
    style.configure("Accent.TButton", background=ACCENT, foreground="white",
                    bordercolor=ACCENT, font=FONT_BOLD)
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#9DB4E6")],
              foreground=[("disabled", "white")])

    style.configure("Danger.TButton", background=DANGER, foreground="white",
                    bordercolor=DANGER, font=FONT_BOLD)
    style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#fca5a5")],
              foreground=[("disabled", "white")])

    style.configure("Inner.TFrame", background=SURFACE)  # frame sin borde dentro de una tarjeta

    style.configure("Treeview", rowheight=30, background=SURFACE, fieldbackground=SURFACE,
                    bordercolor=BORDER, font=FONT)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    style.configure("Treeview.Heading", font=FONT_BOLD, background=ZEBRA, padding=(8, 8),
                    relief="flat", bordercolor=BORDER)
    style.map("Treeview.Heading", background=[("active", ACCENT_SOFT)])
    root.option_add("*TCombobox*Listbox.font", FONT)

    style.configure("TEntry", padding=6, fieldbackground=SURFACE, bordercolor=BORDER)
    style.configure("TCombobox", padding=6, fieldbackground=SURFACE, bordercolor=BORDER)
    style.configure("Status.TLabel", background=BORDER, foreground=TEXT, padding=(12, 4))
