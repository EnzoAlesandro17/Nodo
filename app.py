"""Ventana principal: barra de menús superior + área de contenido + barra de estado."""
import tkinter as tk
from tkinter import ttk

from ui import theme
from ui.screens import (administracion, arqueo, caja, consultas, cuentas, data, estadisticas, gastos, gestiones,
                        ingreso_equipos, inicio, movimientos, nuevo, pendientes, stock, venta_accesorios)

# Estructura del menú, en orden: primero lo que se usa todos los días (cargar, consultar, stock, caja) y al final lo que
# se toca de vez en cuando (administración y data). Cada valor es una lista de opciones.
# Opción: (etiqueta, clase de pantalla[, tecla]) | (etiqueta, [opciones]) = submenú | None = separador
# La tecla (F2...) abre esa pantalla desde cualquier lado; F1 abre el Inicio.
MENU = {
    "Nuevo": [
        ("Accesorios", venta_accesorios.Accesorios, "F2"),
        ("Gestiones", [
            ("CaSIM", gestiones.CaSIM, "F3"),
            ("CaTER", gestiones.CaTER),
            ("Porta", gestiones.Porta),
            ("Regular", gestiones.Regular),
            ("BAF", gestiones.BAF),
        ]),
        None,
        ("Gasto", gastos.Gasto, "F4"),
        ("Transfer", nuevo.Transfer),
        ("Conciliación", nuevo.Conciliacion),
    ],
    "Consultas": [
        ("Ventas y gestiones", consultas.Consultas, "F6"),
        ("Estadísticas", estadisticas.Estadisticas, "F7"),
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
    "Caja": [
        ("Movimientos", caja.Caja, "F5"),
        ("Arqueo de caja", arqueo.Arqueo, "F8"),
    ],
    "Administración": [
        ("Sucursales", administracion.Sucursales),
        ("Empleados", administracion.Empleados),
        ("Cuentas", cuentas.Cuentas),
        None,
        ("Planes", administracion.Planes),
        ("Planes BAF", administracion.PlanesBaf),
        ("Descuentos", administracion.Descuentos),
    ],
    "Data": [
        ("CSV y copia de seguridad", data.Data),
        ("Datos por completar", pendientes.Pendientes),
    ],
}

# Botones del Inicio: (rótulo, tecla, pantalla)
ACCESOS = [
    ("Venta de accesorios", "F2", venta_accesorios.Accesorios),
    ("CaSIM", "F3", gestiones.CaSIM),
    ("Gasto", "F4", gastos.Gasto),
    ("Caja", "F5", caja.Caja),
    ("Ventas y gestiones", "F6", consultas.Consultas),
    ("Estadísticas", "F7", estadisticas.Estadisticas),
    ("Arqueo de caja", "F8", arqueo.Arqueo),
    ("Stock de accesorios", "", stock.StockAccesorios),
    ("Regular", "", gestiones.Regular),
    ("Porta", "", gestiones.Porta),
    ("Ingreso de equipos", "", ingreso_equipos.IngresoEquipos),
    ("CSV y copia de seguridad", "", data.Data),
]


def _atajos(items):
    """[(tecla, pantalla)] de todas las opciones del menú que tienen tecla."""
    for item in items:
        if item is None:
            continue
        if isinstance(item[1], list):
            yield from _atajos(item[1])
        elif len(item) > 2:
            yield item[2], item[1]


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
        self.accesos = ACCESOS   # el Inicio los muestra como botones

        self._build_menubar()
        self.content = ttk.Frame(self)
        self.content.pack(fill="both", expand=True)
        self.status = ttk.Label(self, text="Listo", style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", side="bottom")

        self.current = None
        self.bind_all("<F1>", lambda e: self._show_home())
        for items in MENU.values():
            for tecla, pantalla in _atajos(items):
                self.bind_all(f"<{tecla}>", lambda e, p=pantalla: self.show(p))
        self._show_home()

    def _build_menubar(self):
        bar = tk.Frame(self, bg=theme.BAR)
        bar.pack(fill="x")
        tk.Button(bar, text="Nodo", command=self._show_home, bg=theme.BAR, fg=theme.BAR_FG, activebackground=theme.BAR_HOVER,
                  activeforeground=theme.BAR_FG, font=("Segoe UI", 11, "bold"), bd=0, padx=16, pady=8,
                  cursor="hand2").pack(side="left", padx=(0, 8))   # vuelve al Inicio (F1)

        for name, items in MENU.items():
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
            label, target = item[0], item[1]
            if isinstance(target, list):
                menu.add_cascade(label=label, menu=self._build_menu(menu, target))
            else:
                menu.add_command(label=label, command=lambda s=target: self.show(s),
                                 accelerator=item[2] if len(item) > 2 else "")
        return menu

    def _clear(self):
        if self.current is not None:
            self.current.destroy()

    def _show_home(self):
        self.show(inicio.Inicio)

    def show(self, screen_cls):
        self._clear()
        self.current = screen_cls(self.content)
        self.current.pack(fill="both", expand=True)
        self.status.config(text=screen_cls.title)


if __name__ == "__main__":
    App().mainloop()
