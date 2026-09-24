"""Lo que muestra el Inicio además de los totales: las novedades del día y la agenda (instalaciones de BAF y
portaciones que vienen).

Agenda:
  BAF    las que no están Instaladas, Canceladas ni en Arrepentimiento y tienen fecha: la de instalación si está
         cargada (se reprogramó), si no la pactada. Las que ya pasaron siguen apareciendo, marcadas como atrasadas.
  PORTA  las que tienen fecha de portación de hoy en adelante.
"""
from datetime import date, timedelta

from db import connection, operaciones

ESTADOS_BAF_CERRADOS = ("Instalada", "Cancelada", "Arrepentimiento")


def agenda(hoy=None, dias=14):
    """[{tipo, origen, id, fecha, cliente, detalle, vendedor, atrasada}] de hoy a `dias` días, más las BAF atrasadas,
    ordenadas por fecha."""
    hoy = hoy or date.today()
    hasta = (hoy + timedelta(days=dias)).isoformat()
    marcas = ", ".join("?" * len(ESTADOS_BAF_CERRADOS))
    db = connection.get()
    filas = [dict(r) for r in db.execute(
        "SELECT 'BAF' AS tipo, 'baf' AS origen, g.id, "
        "CASE WHEN g.fecha_instalacion > g.fecha_pactada THEN g.fecha_instalacion ELSE g.fecha_pactada END AS fecha, "
        "g.nombre AS cliente, trim(COALESCE(p.codigo, '') || ' ' || g.franja || ' · ' || g.estado) AS detalle, "
        "COALESCE(e.nombre, '') AS vendedor FROM baf g LEFT JOIN planes p ON p.id = g.plan_id "
        "LEFT JOIN empleados e ON e.id = g.vendedor_id "
        f"WHERE g.activo = 1 AND g.estado NOT IN ({marcas}) AND (g.fecha_pactada <> '' OR g.fecha_instalacion <> '')",
        ESTADOS_BAF_CERRADOS)]
    filas = [f for f in filas if f["fecha"] <= hasta]
    filas += [dict(r) for r in db.execute(
        "SELECT 'PORTA' AS tipo, 'porta' AS origen, g.id, g.fecha_portacion AS fecha, g.nombre AS cliente, "
        "g.numero_portar || ' · ' || p.codigo AS detalle, COALESCE(e.nombre, '') AS vendedor FROM porta g "
        "JOIN planes p ON p.id = g.plan_id LEFT JOIN empleados e ON e.id = g.vendedor_id "
        "WHERE g.activo = 1 AND g.fecha_portacion BETWEEN ? AND ?", (hoy.isoformat(), hasta))]
    for f in filas:
        f["atrasada"] = f["fecha"] < hoy.isoformat()
    return sorted(filas, key=lambda f: (f["fecha"], f["tipo"], f["cliente"]))


def novedades(hoy=None):
    """Lo cargado hoy: {tipo de operación: cantidad} (solo los que tienen), y los arqueos del día."""
    hoy = (hoy or date.today()).isoformat()
    cuenta = {}
    for o in operaciones.operaciones(hoy, hoy, solo_vigentes=True):
        cuenta[o["tipo"]] = cuenta.get(o["tipo"], 0) + 1
    arqueos = connection.get().execute("SELECT count(*) FROM arqueos WHERE activo = 1 AND substr(fecha, 1, 10) = ?",
                                       (hoy,)).fetchone()[0]
    return {"operaciones": {t: cuenta[t] for t in operaciones.TIPOS if t in cuenta}, "arqueos": arqueos}
