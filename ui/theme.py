"""Colores, fuentes y estilos ttk compartidos por toda la app."""
from tkinter import ttk

BG = "#f3f4f6"          # fondo general
SURFACE = "#ffffff"     # tarjetas
BAR = "#1f2937"         # barra superior
BAR_HOVER = "#374151"
BAR_FG = "#f9fafb"
ACCENT = "#2563eb"
ACCENT_HOVER = "#1d4ed8"
TEXT = "#111827"
MUTED = "#6b7280"
BORDER = "#e5e7eb"
DANGER = "#dc2626"
ZEBRA = "#f9fafb"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUB = ("Segoe UI", 10)
FONT_BAR = ("Segoe UI", 11)


def apply(root):
    root.configure(bg=BG)
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
    style.map("TButton", background=[("active", BORDER)])
    style.configure("Accent.TButton", background=ACCENT, foreground="white",
                    bordercolor=ACCENT, font=FONT_BOLD)
    style.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("disabled", "#93c5fd")],
              foreground=[("disabled", "white")])

    style.configure("Danger.TButton", background=DANGER, foreground="white",
                    bordercolor=DANGER, font=FONT_BOLD)
    style.map("Danger.TButton", background=[("active", "#b91c1c"), ("disabled", "#fca5a5")],
              foreground=[("disabled", "white")])

    style.configure("Inner.TFrame", background=SURFACE)  # frame sin borde dentro de una tarjeta

    style.configure("Treeview", rowheight=30, background=SURFACE, fieldbackground=SURFACE,
                    bordercolor=BORDER, font=FONT)
    style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "white")])
    style.configure("Treeview.Heading", font=FONT_BOLD, background="#f9fafb", padding=(8, 8),
                    relief="flat", bordercolor=BORDER)
    style.map("Treeview.Heading", background=[("active", BORDER)])
    root.option_add("*TCombobox*Listbox.font", FONT)

    style.configure("TEntry", padding=6, fieldbackground=SURFACE, bordercolor=BORDER)
    style.configure("TCombobox", padding=6, fieldbackground=SURFACE, bordercolor=BORDER)
    style.configure("Status.TLabel", background=BORDER, foreground=MUTED, padding=(12, 4))
