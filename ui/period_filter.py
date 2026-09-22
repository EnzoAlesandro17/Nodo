"""Filtro por período, reutilizado arriba de cualquier tabla o pantalla con fecha: un solo renglón, con un
modo (Total, Año, Mes o Fechas específicas) y los controles de ese modo al lado. Total, Año y Mes son los
que se usan casi siempre; Fechas específicas queda para cuando hace falta un rango puntual.
"""
import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk

from ui.autocomplete import Combobox
from ui.formatting import fmt_date, parse_date

MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre")
MODOS = ("Total", "Año", "Mes", "Fechas")


def _años_default():
    hoy = date.today().year
    return [str(a) for a in range(hoy, hoy - 6, -1)]


class PeriodFilter:
    """`on_change` se llama cada vez que el período cambia. `rango()` devuelve (desde, hasta) como
    "AAAA-MM-DD" (ambos None si el modo es "Total"). `años`: lista de años a ofrecer (más reciente primero);
    por defecto, los últimos 6. `modo_inicial`: "Total" (por defecto), "Año", "Mes" o "Fechas"."""

    def __init__(self, parent, on_change, años=None, modo_inicial="Total"):
        self.on_change = on_change
        self.años = años or _años_default()
        hoy = date.today()
        self.modo = tk.StringVar(value=modo_inicial)
        self.anio = tk.StringVar(value=str(hoy.year) if str(hoy.year) in self.años else self.años[0])
        self.mes = tk.StringVar(value=MESES[hoy.month - 1])
        self.desde = tk.StringVar(value=fmt_date(hoy.replace(day=1).isoformat()))
        self.hasta = tk.StringVar(value=fmt_date(hoy.isoformat()))

        self.frame = ttk.Frame(parent, style="Inner.TFrame")
        ttk.Label(self.frame, text="Ver", style="Card.TLabel").pack(side="left")
        combo = Combobox(self.frame, textvariable=self.modo, values=MODOS, state="readonly", width=9)
        combo.pack(side="left", padx=(6, 12))
        combo.bind("<<ComboboxSelected>>", lambda e: self._redibujar())
        self.extra = ttk.Frame(self.frame, style="Inner.TFrame")
        self.extra.pack(side="left")
        self._redibujar(avisar=False)

    # --- construcción de los controles según el modo --------------------
    def _redibujar(self, avisar=True):
        for w in self.extra.winfo_children():
            w.destroy()
        modo = self.modo.get()
        if modo == "Año":
            self._combo(self.extra, "", self.anio, self.años, width=7)
        elif modo == "Mes":
            self._combo(self.extra, "", self.mes, MESES, width=11)
            self._combo(self.extra, "de", self.anio, self.años, width=7)
        elif modo == "Fechas":
            ttk.Label(self.extra, text="Desde", style="Card.TLabel").pack(side="left")
            e1 = ttk.Entry(self.extra, textvariable=self.desde, width=11)
            e1.pack(side="left", padx=(6, 12))
            e1.bind("<Return>", lambda e: self.on_change())
            ttk.Label(self.extra, text="Hasta", style="Card.TLabel").pack(side="left")
            e2 = ttk.Entry(self.extra, textvariable=self.hasta, width=11)
            e2.pack(side="left", padx=(6, 0))
            e2.bind("<Return>", lambda e: self.on_change())
        if avisar:
            self.on_change()

    def _combo(self, parent, texto, var, valores, width):
        if texto:
            ttk.Label(parent, text=texto, style="Card.TLabel").pack(side="left", padx=(0, 6))
        box = Combobox(parent, textvariable=var, values=list(valores), state="readonly", width=width)
        box.pack(side="left", padx=(0, 12))
        box.bind("<<ComboboxSelected>>", lambda e: self.on_change())

    def reset(self, modo="Total"):
        """Vuelve al modo indicado (por defecto, "Total"), sin avisar todavía a `on_change`."""
        self.modo.set(modo)
        self._redibujar(avisar=False)

    # --- resultado -------------------------------------------------------
    def rango(self):
        """(desde, hasta) como "AAAA-MM-DD", según el modo elegido. "Fechas" tolera texto vacío o inválido
        de cualquiera de los dos lados (se toma como sin límite de ese lado)."""
        modo = self.modo.get()
        if modo == "Año":
            a = int(self.anio.get())
            return f"{a}-01-01", f"{a}-12-31"
        if modo == "Mes":
            a, m = int(self.anio.get()), MESES.index(self.mes.get()) + 1
            ultimo = calendar.monthrange(a, m)[1]
            return f"{a}-{m:02d}-01", f"{a}-{m:02d}-{ultimo:02d}"
        if modo == "Fechas":
            def valor(var):
                texto = var.get().strip()
                if not texto:
                    return None
                try:
                    return parse_date(texto)
                except ValueError:
                    return None
            return valor(self.desde), valor(self.hasta)
        return None, None   # Total

    def texto(self):
        """Descripción corta del período elegido, para mostrar junto a un total (p. ej. "de agosto de 2026")."""
        modo = self.modo.get()
        if modo == "Total":
            return "de todo el histórico"
        if modo == "Año":
            return f"del año {self.anio.get()}"
        if modo == "Mes":
            return f"de {self.mes.get().lower()} de {self.anio.get()}"
        desde, hasta = self.rango()
        if desde and hasta:
            return f"del {fmt_date(desde)} al {fmt_date(hasta)}"
        if desde:
            return f"desde el {fmt_date(desde)}"
        if hasta:
            return f"hasta el {fmt_date(hasta)}"
        return "de todo el histórico"
