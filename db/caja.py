"""Caja: todos los movimientos de plata, armados a partir de las ventas, gestiones y gastos ya cargados.

Nada se guarda acá: cada consulta lee las tablas de origen (solo registros activos). Cada fila es
{fecha, tipo, monto, cuenta, vendedor, sucursal, detalle}. Los gastos llevan el monto en negativo; los
intereses que cobró el posnet (tipo INTERESES) quedan como filas aparte, no dentro del monto de la venta.

Orígenes:
  VENTA ACCESORIOS  ventas de Nuevo > Accesorios (una fila por pago) y ventas sueltas de Stock > Movimientos
  VENTA EQUIPOS     ventas sueltas de Stock > Movimientos de equipos
  CASIM / CATER     las gestiones que cobran (su movimiento de venta no se cuenta dos veces)
  REGULAR / PORTA / BAF   las gestiones que no cobran: aparecen igual, con monto 0, para que se vea todo lo
                    gestionado en el día
  INTERESES         lo que el posnet cobró de más por las cuotas
  GASTO             Nuevo > Gasto

Las filas de una cuenta de Claro (models.TIPO_FUERA_DE_CAJA) llevan `fuera_de_caja`: se ven, para saber cómo se cobró,
pero esa plata va a Claro y no suma en los totales (ver fuera_de_caja()).
"""
import calendar
from datetime import date, timedelta

from db import connection
from db.administracion import cuentas

TIPO_GASTO, TIPO_INTERESES = "GASTO", "INTERESES"

_VENDEDOR_SUCURSAL = ("LEFT JOIN empleados e ON e.id = {a}.vendedor_id "
                      "LEFT JOIN sucursales s ON s.id = {a}.sucursal_id ")

_ORIGENES = (
    # ventas de Nuevo > Accesorios: una fila por pago
    "SELECT v.fecha, 'VENTA ACCESORIOS' AS tipo, p.monto AS monto, c.codigo AS cuenta, e.nombre AS vendedor, "
    "s.codigo AS sucursal, v.cliente AS detalle "
    "FROM ventas v JOIN pagos p ON p.origen = 'ventas' AND p.mov_id = v.id JOIN cuentas c ON c.id = p.cuenta_id "
    + _VENDEDOR_SUCURSAL.format(a="v") + "WHERE v.activo = 1",
    # sus intereses
    "SELECT v.fecha, 'INTERESES', p.interes, c.codigo, e.nombre, s.codigo, v.cliente "
    "FROM ventas v JOIN pagos p ON p.origen = 'ventas' AND p.mov_id = v.id JOIN cuentas c ON c.id = p.cuenta_id "
    + _VENDEDOR_SUCURSAL.format(a="v") + "WHERE v.activo = 1 AND p.interes > 0",
    # ventas sueltas de Stock > Movimientos (no son de una venta con varios productos ni de una gestión)
    "SELECT m.fecha, 'VENTA ACCESORIOS', m.precio * m.cantidad, m.medio, e.nombre, s.codigo, m.cliente "
    "FROM mov_accesorios m " + _VENDEDOR_SUCURSAL.format(a="m") + "WHERE m.activo = 1 AND m.tipo = 'VENTA' "
    "AND m.venta_id IS NULL",
    # las de CaTER, CaSIM, Regular y Porta (mov_equipos) ya se cuentan en su propia gestión, más abajo
    "SELECT m.fecha, 'VENTA EQUIPOS', m.precio * m.cantidad, m.medio, e.nombre, s.codigo, m.cliente "
    "FROM mov_equipos m " + _VENDEDOR_SUCURSAL.format(a="m") + "WHERE m.activo = 1 AND m.tipo = 'VENTA' "
    "AND m.id NOT IN (SELECT mov_id FROM cater WHERE mov_id IS NOT NULL) "
    "AND m.id NOT IN (SELECT mov_id FROM casim WHERE mov_id IS NOT NULL) "
    "AND m.id NOT IN (SELECT mov_id FROM regular WHERE mov_id IS NOT NULL) "
    "AND m.id NOT IN (SELECT mov_id FROM porta WHERE mov_id IS NOT NULL)",
    # gestiones que cobran
    "SELECT g.fecha, 'CASIM', g.monto, COALESCE(c.codigo, ''), e.nombre, s.codigo, g.nombre || ' ' || g.numero "
    "FROM casim g LEFT JOIN cuentas c ON c.id = g.cuenta_id " + _VENDEDOR_SUCURSAL.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'CATER', p.monto, c.codigo, e.nombre, s.codigo, g.nombre || ' ' || g.numero "
    "FROM cater g JOIN pagos p ON p.origen = 'mov_equipos' AND p.mov_id = g.mov_id JOIN cuentas c ON c.id = p.cuenta_id "
    + _VENDEDOR_SUCURSAL.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'CATER', g.monto, '', e.nombre, s.codigo, g.nombre || ' ' || g.numero "   # sin pagos cargados
    "FROM cater g " + _VENDEDOR_SUCURSAL.format(a="g") + "WHERE g.activo = 1 AND NOT EXISTS "
    "(SELECT 1 FROM pagos p WHERE p.origen = 'mov_equipos' AND p.mov_id = g.mov_id)",
    # gestiones que no cobran (Regular, Porta y BAF): aparecen igual, con monto 0, para que se vea todo lo
    # que se gestionó en el día, no solo lo que movió plata
    "SELECT g.fecha, 'REGULAR', 0.0, '', e.nombre, s.codigo, g.nombre || ' ' || g.numero "
    "FROM regular g " + _VENDEDOR_SUCURSAL.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'PORTA', 0.0, '', e.nombre, s.codigo, g.nombre || ' ' || g.numero_portar "
    "FROM porta g " + _VENDEDOR_SUCURSAL.format(a="g") + "WHERE g.activo = 1",
    "SELECT g.fecha, 'BAF', 0.0, '', COALESCE(e.nombre, ''), '', g.nombre || ' ' || g.telefono "   # BAF no tiene sucursal
    "FROM baf g LEFT JOIN empleados e ON e.id = g.vendedor_id WHERE g.activo = 1",
    # gastos: salen de la caja
    "SELECT g.fecha, 'GASTO', -g.monto, COALESCE(c.codigo, ''), e.nombre, s.codigo, g.detalle "
    "FROM gastos g LEFT JOIN cuentas c ON c.id = g.cuenta_id " + _VENDEDOR_SUCURSAL.format(a="g") + "WHERE g.activo = 1",
)


def movimientos(desde=None, hasta=None):
    """Filas de la caja, la más reciente primero. `desde` y `hasta` ("AAAA-MM-DD", inclusive) son opcionales."""
    where, params = [], []
    if desde:
        where.append("fecha >= ?")
        params.append(desde)
    if hasta:
        where.append("fecha < ?")   # el día de `hasta` entra completo, con su hora
        params.append((date.fromisoformat(hasta) + timedelta(days=1)).isoformat())
    sql = ("SELECT fecha, tipo, monto, cuenta, COALESCE(vendedor, '') AS vendedor, COALESCE(sucursal, '') AS sucursal, "
           "COALESCE(detalle, '') AS detalle FROM (" + " UNION ALL ".join(_ORIGENES) + ")"
           + (f" WHERE {' AND '.join(where)}" if where else "") + " ORDER BY fecha DESC, tipo")
    rows = [dict(r) for r in connection.get().execute(sql, params)]
    de_claro = set(cuentas.fuera_de_caja().values())
    for r in rows:
        r["monto"] = round(r["monto"] or 0.0, 2)
        r["fuera_de_caja"] = r["cuenta"] in de_claro
    return rows


def totales(rows):
    """(ventas, intereses, gastos, neto) de las filas: el neto es lo vendido menos los gastos (sin los intereses).
    Los gastos vienen en positivo. Lo cobrado por Claro no cuenta (ver fuera_de_caja)."""
    rows = [r for r in rows if not r.get("fuera_de_caja")]
    intereses = round(sum(r["monto"] for r in rows if r["tipo"] == TIPO_INTERESES), 2)
    gastos = round(-sum(r["monto"] for r in rows if r["tipo"] == TIPO_GASTO), 2)
    ventas = round(sum(r["monto"] for r in rows if r["tipo"] not in (TIPO_INTERESES, TIPO_GASTO)), 2)
    return ventas, intereses, gastos, round(ventas - gastos, 2)


def fuera_de_caja(rows):
    """Lo cobrado por Claro en las filas: se muestra aparte, no es plata de nuestra caja."""
    return round(sum(r["monto"] for r in rows if r.get("fuera_de_caja")), 2)


def _info_mes(anio, mes):
    """(día al que llegó ese mes, días que tiene). Si `anio`/`mes` es el mes en curso, el día es el de hoy; si no,
    el mes entero ya pasó (o todavía no llegó)."""
    hoy = date.today()
    dias_mes = calendar.monthrange(anio, mes)[1]
    dia = hoy.day if (anio, mes) == (hoy.year, hoy.month) else dias_mes
    return dia, dias_mes


def factor_proyeccion(anio=None, mes=None):
    """Cuánto multiplicar lo que va de un mes para proyectarlo completo: días del mes / día al que llegó.
    Por defecto, el mes en curso."""
    hoy = date.today()
    dia, dias_mes = _info_mes(anio or hoy.year, mes or hoy.month)
    return dias_mes / dia


def proyeccion_mes_actual():
    """Proyección de venta del mes en curso, para Estadísticas: (lo vendido en lo que va del mes / día del
    mes) * días del mes. {anio, mes, dia, dias_mes, ventas, proyectado}."""
    hoy = date.today()
    ventas, *_ = totales(movimientos(hoy.replace(day=1).isoformat(), hoy.isoformat()))
    dia, dias_mes = _info_mes(hoy.year, hoy.month)
    proyectado = round(ventas * factor_proyeccion(hoy.year, hoy.month), 2)
    return {"anio": hoy.year, "mes": hoy.month, "dia": dia, "dias_mes": dias_mes, "ventas": ventas,
            "proyectado": proyectado}
