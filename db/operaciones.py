"""Operaciones (ventas, gestiones y gastos) de todas las tablas, en un solo listado, y las estadísticas.

Cada operación es {fecha, tipo, origen, id, cliente, detalle, monto, unidades, vendedor_id, vendedor, sucursal}:
  origen     la tabla de donde sale (para anularla): ventas, mov_accesorios, mov_equipos, casim, cater, regular, porta,
             baf o gastos
  tipo       ACCESORIOS, EQUIPOS, CASIM, CATER, REGULAR, PORTA, BAF (o GASTO, si se piden los gastos)
  monto      lo vendido (Regular, Porta y BAF no llevan monto); el de un gasto va en positivo
La venta de una SIM que generan CaSIM, Regular y Porta, y la de un equipo que genera CaTER, no se cuentan aparte:
se cuentan en su gestión (igual que en la Caja).
"""
from datetime import date, timedelta

from db import connection

TIPOS = ("ACCESORIOS", "EQUIPOS", "CASIM", "CATER", "REGULAR", "PORTA", "BAF")
TIPO_GASTO = "GASTO"
TIPOS_GESTION = ("CATER", "REGULAR", "PORTA", "BAF")   # CaSIM queda afuera de la matriz de Estadísticas

_JOIN = ("LEFT JOIN empleados e ON e.id = {a}.vendedor_id LEFT JOIN sucursales s ON s.id = {a}.sucursal_id ")
_COLS = "{a}.vendedor_id AS vendedor_id, e.nombre AS vendedor, s.codigo AS sucursal"

_ORIGENES = (
    # venta de Nuevo > Accesorios: una operación por venta (no por pago ni por producto)
    "SELECT v.fecha, 'ACCESORIOS' AS tipo, 'ventas' AS origen, v.id, v.cliente, "
    "(SELECT group_concat(a.codigo, ' + ') FROM mov_accesorios m JOIN accesorios a ON a.id = m.producto_id "
    " WHERE m.venta_id = v.id AND m.activo = 1) AS detalle, "
    "COALESCE((SELECT sum(m.precio * m.cantidad) FROM mov_accesorios m WHERE m.venta_id = v.id AND m.activo = 1), 0) AS monto, "
    "COALESCE((SELECT sum(m.cantidad) FROM mov_accesorios m WHERE m.venta_id = v.id AND m.activo = 1), 0) AS unidades, "
    + _COLS.format(a="v") + " FROM ventas v " + _JOIN.format(a="v") + "WHERE v.activo = 1",
    # ventas sueltas de Stock > Movimientos
    "SELECT m.fecha, 'ACCESORIOS', 'mov_accesorios', m.id, m.cliente, a.codigo || ' - ' || a.descripcion, "
    "m.precio * m.cantidad, m.cantidad, " + _COLS.format(a="m") + " FROM mov_accesorios m "
    "JOIN accesorios a ON a.id = m.producto_id " + _JOIN.format(a="m") + "WHERE m.activo = 1 AND m.tipo = 'VENTA' "
    "AND m.venta_id IS NULL",
    # las de CaTER, CaSIM, Regular y Porta (mov_equipos) ya se cuentan en su propia gestión, más abajo
    "SELECT m.fecha, 'EQUIPOS', 'mov_equipos', m.id, m.cliente, q.codigo || ' - ' || q.descripcion, "
    "m.precio * m.cantidad, m.cantidad, " + _COLS.format(a="m") + " FROM mov_equipos m "
    "JOIN equipos q ON q.id = m.producto_id " + _JOIN.format(a="m") + "WHERE m.activo = 1 AND m.tipo = 'VENTA' "
    "AND m.id NOT IN (SELECT mov_id FROM cater WHERE mov_id IS NOT NULL) "
    "AND m.id NOT IN (SELECT mov_id FROM casim WHERE mov_id IS NOT NULL) "
    "AND m.id NOT IN (SELECT mov_id FROM regular WHERE mov_id IS NOT NULL) "
    "AND m.id NOT IN (SELECT mov_id FROM porta WHERE mov_id IS NOT NULL)",
    # gestiones
    "SELECT g.fecha, 'CASIM', 'casim', g.id, g.nombre, g.numero, g.monto, 1, " + _COLS.format(a="g")
    + " FROM casim g " + _JOIN.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'CATER', 'cater', g.id, g.nombre, g.numero || ' · ' || q.descripcion, g.monto, 1, "
    + _COLS.format(a="g") + " FROM cater g JOIN equipos q ON q.id = g.equipo_id " + _JOIN.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'REGULAR', 'regular', g.id, g.nombre, g.numero || ' · ' || p.codigo, 0.0, 1, "
    + _COLS.format(a="g") + " FROM regular g JOIN planes p ON p.id = g.plan_id " + _JOIN.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'PORTA', 'porta', g.id, g.nombre, g.numero_portar || ' · ' || p.codigo, 0.0, 1, "
    + _COLS.format(a="g") + " FROM porta g JOIN planes p ON p.id = g.plan_id " + _JOIN.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'BAF', 'baf', g.id, g.nombre, COALESCE(p.codigo, '') || ' · ' || g.estado, 0.0, 1, "   # BAF no tiene sucursal
    "g.vendedor_id, e.nombre, '' FROM baf g LEFT JOIN planes_baf p ON p.id = g.plan_id "
    "LEFT JOIN empleados e ON e.id = g.vendedor_id WHERE g.activo = 1 AND {baf}",
)
_GASTOS = ("SELECT g.fecha, 'GASTO', 'gastos', g.id, g.detalle, g.factura, g.monto, 1, " + _COLS.format(a="g")
           + " FROM gastos g " + _JOIN.format(a="g") + "WHERE g.activo = 1")


def operaciones(desde=None, hasta=None, con_gastos=False, solo_vigentes=False):
    """Operaciones entre `desde` y `hasta` ("AAAA-MM-DD", inclusive, opcionales), la más reciente primero.
    `con_gastos`: incluir los gastos. `solo_vigentes`: dejar afuera las BAF canceladas (para las estadísticas)."""
    fuentes = [o.replace("{baf}", "g.estado <> 'Cancelada'" if solo_vigentes else "1") for o in _ORIGENES]
    if con_gastos:
        fuentes.append(_GASTOS)
    where, params = [], []
    if desde:
        where.append("fecha >= ?")
        params.append(desde)
    if hasta:
        where.append("fecha < ?")
        params.append((date.fromisoformat(hasta) + timedelta(days=1)).isoformat())
    sql = ("SELECT * FROM (" + " UNION ALL ".join(fuentes) + ")" + (f" WHERE {' AND '.join(where)}" if where else "")
           + " ORDER BY fecha DESC, id DESC")
    rows = [dict(r) for r in connection.get().execute(sql, params)]
    for r in rows:
        r["monto"] = round(r["monto"] or 0.0, 2)
        r["cliente"], r["detalle"], r["vendedor"], r["sucursal"] = (r[k] or "" for k in ("cliente", "detalle", "vendedor", "sucursal"))
    return rows


def anular(origen, row_id):
    """Da de baja una operación (con su efecto en el stock y en la caja). Devuelve un texto que explica qué pasó."""
    from db import gestiones, movimientos   # acá para evitar importaciones circulares

    if origen == "ventas":   # la venta entera: se anula dando de baja cualquiera de sus productos
        mov = connection.get().execute("SELECT id FROM mov_accesorios WHERE venta_id = ? LIMIT 1", (row_id,)).fetchone()
        if mov:
            movimientos.mov_accesorios.deactivate(mov[0])
        else:   # una venta sin productos activos (ya anulada): solo se marca
            with connection.get() as db:
                db.execute("UPDATE ventas SET activo = 0 WHERE id = ?", (row_id,))
        return "Se anuló la venta: los productos volvieron al stock y sus pagos salieron de la caja."
    repo = {"mov_accesorios": movimientos.mov_accesorios, "mov_equipos": movimientos.mov_equipos,
            "casim": gestiones.casim, "cater": gestiones.cater, "regular": gestiones.regular,
            "porta": gestiones.porta, "baf": gestiones.baf, "gastos": gestiones.gastos}[origen]
    repo.deactivate(row_id)
    if origen in ("mov_accesorios", "mov_equipos", "casim", "cater", "regular", "porta"):
        return "Se dio de baja y el producto volvió al stock."
    return "Se dio de baja."


# --- estadísticas ---------------------------------------------------------------------------------------
def anios():
    """Los años con operaciones (el más reciente primero); siempre incluye el actual."""
    años = {date.today().year} | {int(r["fecha"][:4]) for r in operaciones(con_gastos=True)}
    return sorted(años, reverse=True)


def resumen_gestiones(desde=None, hasta=None):
    """Cantidad de gestiones (CaTER, Regular, Porta y BAF; CaSIM queda afuera) en el período ("AAAA-MM-DD",
    inclusive, opcionales), sin accesorios ni equipos: una matriz de vendedor x tipo de gestión, con el total
    de cada fila y columna. Devuelve (tipos, filas, columnas, monto_total, cantidad_total):
      tipos     siempre los cuatro tipos, en este orden, tengan gestiones o no en el período
      filas     [(vendedor, [cantidad por tipo, en el orden de `tipos`], total de la fila)], por total, de
                mayor a menor
      columnas  total de cada tipo, en el mismo orden
    El monto (lo que cobra CaTER; Regular, Porta y BAF no cobran) va aparte, como un solo total."""
    filas_op = [o for o in operaciones(desde, hasta, solo_vigentes=True) if o["tipo"] in TIPOS_GESTION]
    tipos = list(TIPOS_GESTION)
    matriz = {}
    for o in filas_op:
        fila = matriz.setdefault(o["vendedor"] or "(sin vendedor)", {t: 0 for t in tipos})
        fila[o["tipo"]] += 1
    filas = sorted(((v, [f[t] for t in tipos], sum(f.values())) for v, f in matriz.items()),
                   key=lambda r: (-r[2], r[0]))
    columnas = [sum(f[i] for _, f, _ in filas) for i in range(len(tipos))]
    monto_total = round(sum(o["monto"] for o in filas_op), 2)
    return tipos, filas, columnas, monto_total, len(filas_op)


def top(producto, desde=None, hasta=None, con_sims=False, limite=20):
    """Los productos más vendidos, por unidades, entre `desde` y `hasta` ("AAAA-MM-DD", inclusive, opcionales):
    [{codigo, descripcion, unidades, monto}]. `producto`: "accesorios" o "equipos". La SIM que se entrega en
    cada gestión (accesorios de categoría SIMS, o equipos marca SIM) queda afuera salvo `con_sims`."""
    tabla_mov, tabla_prod = ("mov_accesorios", "accesorios") if producto == "accesorios" else ("mov_equipos", "equipos")
    filtro_sim = "p.categoria <> 'SIMS'" if producto == "accesorios" else "p.marca <> 'SIM'"
    where, params = ["m.activo = 1", "m.tipo = 'VENTA'"], []
    if desde:
        where.append("m.fecha >= ?")
        params.append(desde)
    if hasta:
        where.append("m.fecha < ?")
        params.append((date.fromisoformat(hasta) + timedelta(days=1)).isoformat())
    if not con_sims:
        where.append(filtro_sim)
    sql = (f"SELECT p.codigo, p.descripcion, sum(m.cantidad) AS unidades, round(sum(m.precio * m.cantidad), 2) AS monto "
           f"FROM {tabla_mov} m JOIN {tabla_prod} p ON p.id = m.producto_id "
           f"WHERE {' AND '.join(where)} GROUP BY p.id ORDER BY unidades DESC, monto DESC, p.codigo LIMIT ?")
    params.append(limite)
    return [dict(r) for r in connection.get().execute(sql, params)]
