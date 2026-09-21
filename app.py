"""Ventana principal: barra de menús superior + área de contenido + barra de estado."""
import tkinter as tk
from tkinter import ttk

from ui import theme
from ui.screens import (administracion, caja, cuentas, data, gastos, gestiones, ingreso_equipos, movimientos, nuevo,
                        stock, venta_accesorios)

# Estructura del menú, en orden. Cada valor es una lista de opciones o, si el menú
# no tiene opciones, directamente la clase de pantalla.
# Opción: (etiqueta, clase de pantalla) | (etiqueta, [opciones]) = submenú | None = separador
MENU = {
    "Administración": [
        ("Sucursales", administracion.Sucursales),
        ("Empleados", administracion.Empleados),
        None,
        ("Planes", administracion.Planes),
        ("Planes BAF", administracion.PlanesBaf),
        ("Descuentos", administracion.Descuentos),
    ],
    "Nuevo": [
        ("Accesorios", venta_accesorios.Accesorios),
        ("Gestiones", [
            ("CaSIM", gestiones.CaSIM),
            ("CaTER", gestiones.CaTER),
            ("Porta", gestiones.Porta),
            ("Regular", gestiones.Regular),
            ("BAF", gestiones.BAF),
        ]),
        None,
        ("Gasto", gastos.Gasto),
        ("Transfer", nuevo.Transfer),
        ("Conciliación", nuevo.Conciliacion),
        None,
        ("Consultas", nuevo.Consultas),
    ],
    "Stock": [
        ("Accesorios", stock.StockAccesorios),
        ("Equipos", stock.StockEquipos),
        None,
        ("Movimientos", [
            ("Accesorios", movimientos.MovAccesorios),
            ("Equipos", movimientos.MovEquipos),
        ]),
        ("Ingreso de equipos", ingreso_equipos.IngresoEquipos),
    ],
    "Cuentas": cuentas.Cuentas,
    "Caja": caja.Caja,
    "Data": data.Data,
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Nodo")
        self.minsize(800, 520)
        w, h = 1200, 650
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        theme.apply(self)

        self._build_menubar()
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.status = ttk.Label(self, text="Listo", style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", side="bottom")

        self.current = None
        self._show_home()

    def _build_menubar(self):
        bar = tk.Frame(self, bg=theme.BAR)
        bar.pack(fill="x")
        tk.Label(bar, text="Nodo", bg=theme.BAR, fg=theme.BAR_FG,
                 font=("Segoe UI", 11, "bold")).pack(side="left", padx=(16, 24), pady=10)

        for name, items in MENU.items():
            if not isinstance(items, list):  # menú sin opciones: abre su pantalla directo
                tk.Button(bar, text=name, command=lambda s=items: self.show(s), bg=theme.BAR,
                          fg=theme.BAR_FG, activebackground=theme.BAR_HOVER,
                          activeforeground=theme.BAR_FG, font=theme.FONT_BAR, bd=0, padx=14,
                          pady=8, cursor="hand2").pack(side="left")
                continue
            btn = tk.Menubutton(bar, text=name + "  ▾", bg=theme.BAR, fg=theme.BAR_FG,
                                activebackground=theme.BAR_HOVER, activeforeground=theme.BAR_FG,
                                font=theme.FONT_BAR, bd=0, padx=14, pady=8, cursor="hand2")
            btn["menu"] = self._build_menu(btn, items)
            btn.pack(side="left")

    def _build_menu(self, parent, items):
        menu = tk.Menu(parent, tearoff=0, font=theme.FONT_BAR, bg="white", fg=theme.TEXT,
                       activebackground=theme.ACCENT, activeforeground="white", bd=0)
        for item in items:
            if item is None:
                menu.add_separator()
                continue
            label, target = item
            if isinstance(target, list):
                menu.add_cascade(label=label, menu=self._build_menu(menu, target))
            else:
                menu.add_command(label=label, command=lambda s=target: self.show(s))
        return menu

    def _clear(self):
        if self.current is not None:
            self.current.destroy()

    def _show_home(self):
        self._clear()
        home = ttk.Frame(self.content)
        holder = ttk.Frame(home)
        holder.place(relx=0.5, rely=0.45, anchor="center")
        ttk.Label(holder, text="Nodo", style="Title.TLabel").pack()
        ttk.Label(holder, text="Elegí una opción del menú superior para empezar",
                  style="Sub.TLabel").pack(pady=(4, 0))
        home.pack(fill="both", expand=True)
        self.current = home

    def show(self, screen_cls):
        self._clear()
        self.current = screen_cls(self.content)
        self.current.pack(fill="both", expand=True)
        self.status.config(text=screen_cls.title)


if __name__ == "__main__":
    App().mainloop()
