"""Comportamiento extra para los campos de texto: escribir en mayúsculas y Ctrl+Z / Ctrl+Y."""
import time
import tkinter as tk


def force_upper(widget):
    """Lo que se escribe o pega aparece directamente en mayúsculas (sin pasar por minúscula)."""

    def typed(event):
        if len(event.char) != 1 or not event.char.isprintable():
            return None   # teclas de control, flechas, atajos: comportamiento normal
        _replace_selection(event.widget, event.char.upper())
        return "break"

    def pasted(event):
        try:
            text = event.widget.clipboard_get()
        except tk.TclError:
            return "break"
        _replace_selection(event.widget, text.replace("\r", "").replace("\n", " ").upper())
        return "break"

    widget.bind("<KeyPress>", typed)
    widget.bind("<<Paste>>", pasted)


def _replace_selection(widget, text):
    if widget.selection_present():
        widget.delete("sel.first", "sel.last")
    widget.insert("insert", text)


class Undo:
    """Deshacer (Ctrl+Z) y rehacer (Ctrl+Y o Ctrl+Mayús+Z) para un campo ligado a una StringVar.

    Los cambios seguidos (escribir una palabra, mantener Borrar) se deshacen de una vez.
    """
    GROUP_SECONDS = 0.6

    def __init__(self, widget, var):
        self.widget, self.var = widget, var
        self.past, self.future = [], []
        self.value = var.get()
        self.stamp = 0.0
        self.applying = False
        var.trace_add("write", self._changed)
        for key in ("z", "Z"):
            widget.bind(f"<Control-KeyPress-{key}>", self._on_z)
        for key in ("y", "Y"):
            widget.bind(f"<Control-KeyPress-{key}>", lambda e: self._restore(self.future, self.past))

    def _changed(self, *_):
        if self.applying or self.var.get() == self.value:
            return
        now = time.monotonic()
        if not self.past or now - self.stamp > self.GROUP_SECONDS:
            self.past.append(self.value)
        self.stamp = now
        self.value = self.var.get()
        self.future.clear()

    def _on_z(self, event):
        shift = event.state & 0x1
        return self._restore(self.future, self.past) if shift else self._restore(self.past, self.future)

    def _restore(self, source, other):
        if source:
            other.append(self.value)
            self.value = source.pop()
            self.applying = True
            self.var.set(self.value)
            self.applying = False
            self.widget.icursor("end")
            self.stamp = 0.0
        return "break"
