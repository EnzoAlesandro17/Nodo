"""Filtro por período, el mismo en todas las pantallas con fecha: Año y Mes (listas) y, a su derecha, el rango
Desde / Hasta. Elegir un año o un mes completa el rango solo; escribir un rango a mano (Enter o salir del campo)
deja Año y Mes en blanco, salvo que el rango sea justo un año o un mes. Va a la derecha del renglón de Buscar.
"""
import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk

from ui.autocomplete import Combobox
from ui.formatting import fmt_date, parse_date

MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre",
         "Noviembre", "Diciembre")
TODOS = "TODOS"


def _años_default():
    hoy = date.today().year
    return [str(a) for a in range(hoy, hoy - 6, -1)]


def _limites(anio, mes=None):
    """(desde, hasta) "AAAA-MM-DD" del año entero o de ese mes (1 a 12)."""
    if mes is None:
        return f"{anio}-01-01", f"{anio}-12-31"
    return f"{anio}-{mes:02d}-01", f"{anio}-{mes:02d}-{calendar.monthrange(anio, mes)[1]:02d}"


class PeriodFilter:
    """`on_change` se llama cada vez que el período cambia. `rango()` devuelve (desde, hasta) como "AAAA-MM-DD"
    (None del lado que no tiene límite). `años`: años a ofrecer (más reciente primero); por defecto, los últimos 6.
    `modo_inicial`: "Total" (sin límite, por defecto), "Año" (el actual) o "Mes" (el actual)."""

    def __init__(self, parent, on_change, años=None, modo_inicial="Total"):
        self.on_change = on_change
        self.años = años or _años_default()
        self.modo_inicial = modo_inicial
        self.anio, self.mes = tk.StringVar(), tk.StringVar()
        self.desde, self.hasta = tk.StringVar(), tk.StringVar()

        self.frame = ttk.Frame(parent, style="Inner.TFrame")
        ttk.Label(self.frame, text="Año", style="Card.TLabel").pack(side="left")
        box = Combobox(self.frame, textvariable=self.anio, values=[TODOS] + list(self.años), state="readonly", width=7)
        box.pack(side="left", padx=(6, 10))
        box.bind("<<ComboboxSelected>>", lambda e: self._elegir_anio())
        ttk.Label(self.frame, text="Mes", style="Card.TLabel").pack(side="left")
        box = Combobox(self.frame, textvariable=self.mes, values=[TODOS] + list(MESES), state="readonly", width=10)
        box.pack(side="left", padx=(6, 14))
        box.bind("<<ComboboxSelected>>", lambda e: self._elegir_mes())
        for texto, var, pad in (("Desde", self.desde, 8), ("Hasta", self.hasta, 0)):
            ttk.Label(self.frame, text=texto, style="Card.TLabel").pack(side="left")
            e = ttk.Entry(self.frame, textvariable=var, width=10)
            e.pack(side="left", padx=(6, pad))
            e.bind("<Return>", lambda ev: self._rango_a_mano())
            e.bind("<FocusOut>", lambda ev: self._rango_a_mano())
        self.reset()

    # --- cambios -----------------------------------------------------------
    def _elegir_anio(self):
        if self.anio.get() == TODOS:
            self.mes.set(TODOS)
        self._completar_rango()

    def _elegir_mes(self):
        if self.mes.get() != TODOS and self.anio.get() in ("", TODOS):   # un mes sin año: el del año actual
            actual = str(date.today().year)
            self.anio.set(actual if actual in self.años else self.años[0])
        self._completar_rango()

    def _completar_rango(self, avisar=True):
        """Pone en Desde / Hasta el año o el mes elegido (vacíos con Año TODOS)."""
        anio, mes = self.anio.get(), self.mes.get()
        if anio in ("", TODOS):
            desde = hasta = ""
        else:
            desde, hasta = _limites(int(anio), MESES.index(mes) + 1 if mes in MESES else None)
        self.desde.set(fmt_date(desde))
        self.hasta.set(fmt_date(hasta))
        self._ultimo = self.rango()
        if avisar:
            self.on_change()

    def _rango_a_mano(self):
        rango = self.rango()
        if rango == self._ultimo:   # salir del campo sin cambiar nada no vuelve a filtrar
            return
        self._ultimo = rango
        self.anio.set("")
        self.mes.set("")
        desde, hasta = rango
        if desde is None and hasta is None:
            self.anio.set(TODOS)
            self.mes.set(TODOS)
        elif desde and hasta and desde[:4] == hasta[:4] and desde[:4] in self.años:   # justo un año o un mes
            anio = int(desde[:4])
            if (desde, hasta) == _limites(anio):
                self.anio.set(str(anio))
                self.mes.set(TODOS)
            elif desde[:7] == hasta[:7] and (desde, hasta) == _limites(anio, int(desde[5:7])):
                self.anio.set(str(anio))
                self.mes.set(MESES[int(desde[5:7]) - 1])
        self.on_change()

    def reset(self):
        """Vuelve al período inicial, sin avisar todavía a `on_change`."""
        hoy = date.today()
        actual = str(hoy.year) if str(hoy.year) in self.años else self.años[0]
        self.anio.set(TODOS if self.modo_inicial == "Total" else actual)
        self.mes.set(MESES[hoy.month - 1] if self.modo_inicial == "Mes" else TODOS)
        self._completar_rango(avisar=False)

    # --- resultado -------------------------------------------------------
    def rango(self):
        """(desde, hasta) como "AAAA-MM-DD". Un lado vacío o mal escrito se toma como sin límite de ese lado."""
        def valor(var):
            texto = var.get().strip()
            if not texto:
                return None
            try:
                return parse_date(texto)
            except ValueError:
                return None
        return valor(self.desde), valor(self.hasta)

    def mes_elegido(self):
        """(año, mes) si el período es justo un mes entero (Año y Mes elegidos); si no, None."""
        if self.anio.get() in ("", TODOS) or self.mes.get() not in MESES:
            return None
        return int(self.anio.get()), MESES.index(self.mes.get()) + 1

    def texto(self):
        """Descripción corta del período elegido, para mostrar junto a un total (p. ej. "de agosto de 2026")."""
        anio, mes = self.anio.get(), self.mes.get()
        if anio not in ("", TODOS):
            return f"de {mes.lower()} de {anio}" if mes in MESES else f"del año {anio}"
        desde, hasta = self.rango()
        if desde and hasta:
            return f"del {fmt_date(desde)} al {fmt_date(hasta)}"
        if desde:
            return f"desde el {fmt_date(desde)}"
        if hasta:
            return f"hasta el {fmt_date(hasta)}"
        return "de todo el histórico"
