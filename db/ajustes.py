"""Datos sueltos de la app guardados en la propia base (tabla `ajustes`: clave y valor)."""
from db import connection


def leer(clave, por_defecto=""):
    row = connection.get().execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return row[0] if row else por_defecto


def guardar(clave, valor):
    db = connection.get()
    with db:
        db.execute("INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
                   "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, valor))
