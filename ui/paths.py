"""Carpetas donde proponer guardar y abrir archivos."""
from pathlib import Path


def escritorio():
    """La carpeta del escritorio del usuario (o su carpeta personal, si no se encuentra)."""
    home = Path.home()
    for carpeta in (home / "Desktop", home / "OneDrive" / "Desktop", home / "Escritorio"):
        if carpeta.is_dir():
            return str(carpeta)
    return str(home)
