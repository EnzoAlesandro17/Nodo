"""IMEI de los equipos: un registro por unidad, ligado al modelo (equipo) y a la sucursal donde está.

Cargar o quitar un IMEI no modifica el stock del modelo: el stock se mueve en los movimientos.
Una venta con IMEI (Stock > Movimientos de equipos o CaTER) da de baja el IMEI cargado, y si la venta se
edita o se anula, vuelve.
"""
from datetime import date

from db import connection


def _db():
    return connection.get()


def de_equipo(equipo_id):
    """IMEI activos del modelo, los más antiguos primero. Cada fila trae `sucursal` (nombre clave) y `dias`."""
    rows = _db().execute(
        "SELECT i.id, i.imei, i.sucursal_id, s.codigo AS sucursal, i.fecha_ingreso, i.remito FROM imeis i "
        "LEFT JOIN sucursales s ON s.id = i.sucursal_id WHERE i.equipo_id = ? AND i.activo = 1 "
        "ORDER BY i.fecha_ingreso, i.id", (equipo_id,)).fetchall()
    hoy = date.today()
    return [dict(r, dias=(hoy - date.fromisoformat(r["fecha_ingreso"])).days) for r in rows]


def resumen_por_equipo():
    """{equipo_id: (cantidad, días del más antiguo)} de los IMEI activos."""
    hoy = date.today()
    return {r["equipo_id"]: (r["n"], (hoy - date.fromisoformat(r["f"])).days)
            for r in _db().execute("SELECT equipo_id, COUNT(*) AS n, MIN(fecha_ingreso) AS f FROM imeis "
                                   "WHERE activo = 1 GROUP BY equipo_id")}


def buscar(imei):
    """El registro del IMEI (activo o no), con el código y la descripción de su modelo; None si no está cargado."""
    row = _db().execute("SELECT i.id, i.equipo_id, i.activo, i.salida, e.codigo, e.descripcion FROM imeis i "
                        "JOIN equipos e ON e.id = i.equipo_id WHERE i.imei = ?", (imei,)).fetchone()
    return dict(row) if row else None


# Las dos siguientes no confirman la transacción: las usan los movimientos de venta.
def tomar(imei, salida):
    """La venta `salida` ("tabla:id") saca el IMEI del stock (si estaba cargado y activo)."""
    _db().execute("UPDATE imeis SET activo = 0, salida = ? WHERE imei = ? AND activo = 1", (salida, imei))


def soltar(salida):
    """Se revierte la venta `salida`: el IMEI que sacó vuelve al stock."""
    _db().execute("UPDATE imeis SET activo = 1, salida = '' WHERE salida = ?", (salida,))


def _guardar(db, equipo_id, imei, sucursal_id, fecha_ingreso, remito):
    """Carga o reactiva un IMEI sin confirmar la transacción. ValueError si ya está cargado."""
    row = db.execute("SELECT i.id, i.activo, e.codigo, e.descripcion FROM imeis i "
                     "JOIN equipos e ON e.id = i.equipo_id WHERE i.imei = ?", (imei,)).fetchone()
    if row and row["activo"]:
        raise ValueError(f"El IMEI {imei} ya está cargado en {row['codigo']} - {row['descripcion']}.")
    if row:   # un IMEI quitado o vendido que vuelve a entrar
        db.execute("UPDATE imeis SET equipo_id = ?, sucursal_id = ?, fecha_ingreso = ?, remito = ?, activo = 1, "
                   "salida = '' WHERE id = ?", (equipo_id, sucursal_id, fecha_ingreso, remito, row["id"]))
        return row["id"]
    return db.execute("INSERT INTO imeis (equipo_id, imei, sucursal_id, fecha_ingreso, remito) VALUES (?, ?, ?, ?, ?)",
                      (equipo_id, imei, sucursal_id, fecha_ingreso, remito)).lastrowid


def agregar(equipo_id, imei, sucursal_id, fecha_ingreso, remito=""):
    """Carga un IMEI. ValueError (con el motivo) si ya está cargado. Un IMEI quitado se reactiva."""
    db = _db()
    with db:
        return _guardar(db, equipo_id, imei, sucursal_id, fecha_ingreso, remito)


def quitar(imei_id):
    with _db() as db:
        db.execute("UPDATE imeis SET activo = 0 WHERE id = ?", (imei_id,))
