"""Diálogos de la copia de seguridad (los usan Data y el Inicio)."""
import sqlite3
from datetime import datetime
from tkinter import filedialog, messagebox

from db import backup
from ui.paths import escritorio


def hacer_copia(parent):
    """Pregunta dónde guardar (proponiendo el Escritorio) y guarda la copia de la base. True si se hizo."""
    destino = filedialog.asksaveasfilename(
        parent=parent, title="Copia de seguridad: elegí dónde guardarla", defaultextension=".db",
        initialdir=escritorio(), initialfile=backup.nombre_sugerido(), filetypes=[("Base de datos de Nodo", "*.db")])
    if not destino:
        return False
    if backup.dentro_de_data(destino):
        messagebox.showwarning("Copia de seguridad", "No la guardes en la carpeta de la base (data): ahí tiene que haber un "
                               "solo archivo, nodo.db. Elegí el Escritorio u otra carpeta.", parent=parent)
        return False
    try:
        tamano = backup.copiar(destino)
    except (OSError, sqlite3.Error) as e:
        messagebox.showerror("No se pudo hacer la copia", str(e), parent=parent)
        return False
    messagebox.showinfo("Copia lista", f"Se guardó la copia ({tamano / 1024:.0f} KB), ya verificada:\n\n{destino}\n\n"
                        "Es un solo archivo: subilo a Drive o copialo a la carpeta data de otra PC como nodo.db.", parent=parent)
    return True


def texto_ultima_copia():
    """('Última copia: hace 3 días (18/09/2026)', hay_que_avisar) para mostrar en pantalla."""
    ultima = backup.ultima_copia()
    if ultima is None:
        return "Todavía no hiciste ninguna copia de seguridad desde Nodo.", True
    dias = (datetime.now().date() - ultima.date()).days
    cuando = "hoy" if dias == 0 else "ayer" if dias == 1 else f"hace {dias} días"
    return f"Última copia: {cuando} ({ultima:%d/%m/%Y %H:%M}).", dias > 7
