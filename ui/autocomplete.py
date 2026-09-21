"""Desplegable que va recomendando mientras se escribe (lo usan todos los desplegables de la app).

`Combobox` es un ttk.Combobox: se le pasan `values`, `textvariable`, etc. y sigue generando <<ComboboxSelected>>.
Al escribir se abre debajo del campo la lista de opciones que contienen todas las palabras escritas (sin importar
mayúsculas ni acentos, las que empiezan igual primero). El foco nunca sale del campo, así que se puede seguir escribiendo:
  ↑ ↓          recorren la lista (con la lista cerrada, la abren completa)
  Enter        elige la opción marcada (la primera, si no se movió)
  clic         elige la opción tocada
  Esc          cierra la lista
La flecha del campo sigue abriendo el desplegable común.

Con state="readonly" (listas cerradas: sucursal, vendedor, cuenta...) también se puede escribir, pero el campo solo
admite las opciones de la lista: al salir (o con Enter) lo escrito se completa si coincide con una sola opción, y si no
vuelve a lo que había. Un clic en el campo abre la lista completa, como antes.
"""
import tkinter as tk
import unicodedata
from tkinter import font as tkfont
from tkinter import ttk

from ui import theme

TAG = "AutoCombobox"
FILAS = 8            # cuántas opciones se ven a la vez en la lista de sugerencias
ANCHO_MAX = 720      # ancho máximo de la lista, en píxeles
NAVEGACION = {"Up", "Down", "Left", "Right", "Home", "End", "Prior", "Next", "Return", "KP_Enter", "Escape", "Tab",
              "ISO_Left_Tab", "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Num_Lock",
              "Menu", "Insert"}


def normalizar(text):
    """Mayúsculas y sin acentos, para comparar."""
    return "".join(c for c in unicodedata.normalize("NFD", text.upper()) if not unicodedata.combining(c))


class Combobox(ttk.Combobox):
    _registrado = False

    def __init__(self, master=None, *, max_items=200, **kw):
        self.cerrado = kw.get("state") == "readonly"   # lista cerrada: solo se admiten las opciones
        if self.cerrado:
            kw["state"] = "normal"   # para poder escribir; lo escrito se valida contra las opciones
        super().__init__(master, **kw)
        self.max_items = max_items
        self._popup = self._lista = self._afuera = None
        self._coincidencias = []
        self._cache = (None, [])   # (values, [(opción, opción normalizada)])
        self._al_entrar = ""
        self.bindtags((TAG,) + self.bindtags())   # antes que los bindings propios del campo
        if not Combobox._registrado:
            Combobox._registrado = True
            for seq, name in (("<KeyRelease>", "_al_soltar"), ("<KeyPress-Down>", "_abajo"), ("<KeyPress-Up>", "_arriba"),
                              ("<KeyPress-Return>", "_enter"), ("<KeyPress-KP_Enter>", "_enter"),
                              ("<KeyPress-Escape>", "_escape"), ("<ButtonPress-1>", "_clic"), ("<FocusIn>", "_foco"),
                              ("<FocusOut>", "_sin_foco")):
                self.bind_class(TAG, seq, lambda e, name=name: getattr(e.widget, name)(e))

    # --- opciones ------------------------------------------------------
    def _opciones(self):
        values = self.tk.splitlist(self.cget("values"))
        if values != self._cache[0]:
            self._cache = (values, [(v, normalizar(v)) for v in values if v])
        return self._cache[1]

    def _buscar(self, texto):
        """Las opciones que contienen todas las palabras de `texto`, las que empiezan igual primero."""
        q = normalizar(texto).strip()
        if not q:
            return [v for v, _ in self._opciones()][:self.max_items]
        palabras = q.split()
        hallados = []
        for orden, (v, n) in enumerate(self._opciones()):
            if all(p in n for p in palabras):
                rango = 0 if q in (n, n.split(" - ", 1)[0]) else 1 if n.startswith(q) else 2   # 0: el código exacto
                hallados.append((rango, orden, v))
        hallados.sort()
        return [v for _, _, v in hallados[:self.max_items]]

    def resolver(self):
        """La opción que es lo escrito: vacío si no hay nada, la opción si coincide con una sola, None si no."""
        texto = self.get().strip()
        if not texto:
            return ""
        n = normalizar(texto)
        for v, vn in self._opciones():
            if vn == n:
                return v
        hallados = self._buscar(texto)
        return hallados[0] if len(hallados) == 1 else None

    def confirmar(self, volver=False):
        """Lista cerrada: completa lo escrito con la opción que corresponde (y avisa con <<ComboboxSelected>>).
        Si no coincide con ninguna, deja el campo vacío, o (`volver`) como estaba al entrar."""
        if not self.cerrado or not self.winfo_exists():
            return
        elegido = self.resolver()
        if elegido is None:
            self.set(self._al_entrar if volver else "")
        elif elegido != self.get():
            self.set(elegido)
            self.event_generate("<<ComboboxSelected>>")

    # --- lista de sugerencias ------------------------------------------
    def _abierto(self):
        return self._popup is not None and self._popup.winfo_ismapped()

    def _sugerir(self, todas=False):
        actual = self.get()
        self._coincidencias = [v for v, _ in self._opciones()][:self.max_items] if todas else self._buscar(actual)
        if not self._coincidencias or (not todas and not actual.strip()):
            return self._cerrar()
        if self._popup is None:
            self._popup = tk.Toplevel(self)
            self._popup.withdraw()
            self._popup.wm_overrideredirect(True)
            self._popup.attributes("-topmost", True)
            self._lista = tk.Listbox(self._popup, activestyle="none", exportselection=False, selectmode="browse", bd=0,
                                     font=theme.FONT, highlightthickness=1, highlightbackground=theme.BORDER,
                                     selectbackground=theme.ACCENT, selectforeground="white", takefocus=0)
            self._lista.pack(fill="both", expand=True)
            self._lista.bind("<Button-1>", self._tocar)
            self._lista.bind("<Motion>", lambda e: self._marcar(self._lista.nearest(e.y)))
            self._lista.bind("<MouseWheel>", lambda e: self._lista.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        self._lista.delete(0, "end")
        self._lista.insert("end", *self._coincidencias)
        indice = self._coincidencias.index(actual) if todas and actual in self._coincidencias else 0
        self._marcar(indice)
        self._colocar()
        if self._afuera is None:   # un clic en cualquier otro lado de la ventana cierra la lista
            top = self.winfo_toplevel()
            self._afuera = (top, top.bind("<ButtonPress>", self._clic_afuera, add="+"))

    def _colocar(self):
        fuente = tkfont.Font(font=theme.FONT)
        filas = min(len(self._coincidencias), FILAS)
        ancho = max(self.winfo_width(), min(max(fuente.measure(v) for v in self._coincidencias) + 30, ANCHO_MAX))
        alto = filas * (fuente.metrics("linespace") + 3) + 4
        self._lista.configure(height=filas)
        x, y = self.winfo_rootx(), self.winfo_rooty() + self.winfo_height()
        if y + alto > self.winfo_screenheight():   # no entra abajo: se abre hacia arriba
            y = self.winfo_rooty() - alto
        self._popup.geometry(f"{ancho}x{alto}+{x}+{y}")
        self._popup.deiconify()
        self._popup.lift()

    def _cerrar(self):
        if self._popup is not None:
            try:
                self._popup.withdraw()
            except tk.TclError:   # la ventana ya se cerró con la lista abierta
                self._popup = None
        if self._afuera is not None:
            top, funcid = self._afuera
            self._afuera = None
            try:
                top.unbind("<ButtonPress>", funcid)
            except tk.TclError:
                pass

    def _marcar(self, indice):
        self._lista.selection_clear(0, "end")
        self._lista.selection_set(indice)
        self._lista.activate(indice)
        self._lista.see(indice)

    def _elegir(self, indice):
        self.set(self._coincidencias[indice])
        self._cerrar()
        self.icursor("end")
        self.event_generate("<<ComboboxSelected>>")

    def _tocar(self, event):
        self._elegir(self._lista.nearest(event.y))
        self.focus_set()
        return "break"

    def _clic_afuera(self, event):
        if not self.winfo_exists():
            return
        if event.widget is not self and not str(event.widget).startswith(str(self._popup)):
            self._cerrar()

    # --- eventos del campo ---------------------------------------------
    def _al_soltar(self, event):
        if event.keysym in NAVEGACION or event.keysym.startswith("F") and event.keysym[1:].isdigit():
            return
        if str(self.cget("state")) == "normal":
            self._sugerir()

    def _mover(self, paso):
        if str(self.cget("state")) != "normal":
            return None
        if not self._abierto():
            self._sugerir(todas=True)
        else:
            self._marcar(max(0, min(len(self._coincidencias) - 1, self._lista.index("active") + paso)))
        return "break"

    def _abajo(self, event):   # con la lista cerrada, la abre completa
        return self._mover(1)

    def _arriba(self, event):
        return self._mover(-1)

    def _enter(self, event):
        if self._abierto():
            self._elegir(self._lista.index("active"))
            return "break"
        self.confirmar(volver=True)   # sin lista abierta, Enter sigue su camino (guardar, pasar al campo siguiente...)
        return None

    def _escape(self, event):
        if self._abierto():
            self._cerrar()
            return "break"
        return None

    def _clic(self, event):
        if not self.cerrado or str(self.cget("state")) != "normal":
            self._cerrar()
            return None
        if event.x >= self.winfo_width() - 24:   # la flecha: el desplegable común
            self._cerrar()
            return None
        self.focus_set()
        self.select_range(0, "end")
        self.icursor("end")
        self._sugerir(todas=True)
        return "break"

    def _foco(self, event):
        self._al_entrar = self.get()

    def _sin_foco(self, event):
        self._cerrar()
        self.confirmar(volver=True)
