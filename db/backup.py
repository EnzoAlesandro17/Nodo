"""Copia de seguridad: un solo archivo con toda la base, hecha con la API de copia de SQLite.

Es segura con la app abierta (una copia del archivo a mano, mientras se escribe, puede salir corrupta) y la copia
queda como un .db común, que se puede abrir con Nodo o copiar a data/nodo.db en otra PC.
"""
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from db import ajustes, connection

CLAVE = "ultima_copia"   # ajuste con "AAAA-MM-DD HH:MM:SS" de la última copia


def carpeta_de_la_base():
    return Path(os.environ.get("NODO_DB", connection.DEFAULT_PATH)).parent


def dentro_de_data(destino):
    """True si el destino está en la carpeta de la base (ahí tiene que haber un solo archivo: nodo.db)."""
    return Path(destino).resolve().parent == carpeta_de_la_base().resolve()


def nombre_sugerido():
    return f"nodo_{datetime.now():%Y-%m-%d}.db"


def copiar(destino):
    """Guarda la copia en `destino` y devuelve su tamaño en bytes. Falla (OSError / sqlite3.Error) sin dejar el
    archivo a medias. Deja anotado el momento en la propia base, así también figura en la copia."""
    destino = Path(destino)
    anterior = ajustes.leer(CLAVE, "")
    ajustes.guardar(CLAVE, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    parcial = destino.with_name(destino.name + ".parcial")
    try:
        parcial.unlink(missing_ok=True)
        dst = sqlite3.connect(parcial)
        try:
            connection.get().backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("La copia no pasó la verificación de integridad.")
        finally:
            dst.close()
        parcial.replace(destino)
    except Exception:
        parcial.unlink(missing_ok=True)
        ajustes.guardar(CLAVE, anterior)
        raise
    return destino.stat().st_size


def ultima_copia():
    """datetime de la última copia hecha desde la app, o None si nunca se hizo."""
    valor = ajustes.leer(CLAVE, "")
    try:
        return datetime.strptime(valor, "%Y-%m-%d %H:%M:%S") if valor else None
    except ValueError:
        return None
