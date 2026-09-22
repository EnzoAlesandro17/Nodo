"""Datos por completar: lo que quedó cargado a medias o con un dato dudoso, agrupado por categoría.

Cada categoría es {clave, titulo, columnas: [(campo, rótulo, ancho)], filas: [{id, ...}]}; `id` es el del registro en su
tabla, para abrirlo y corregirlo. Se calcula al momento, así que lo que se corrige sale solo de la lista.
"""
from db import connection


def _rows(sql, params=()):
    return [dict(r) for r in connection.get().execute(sql, params)]


def _regular():
    return _rows("SELECT g.id, g.fecha, g.nombre, g.numero, p.codigo AS plan, COALESCE(e.nombre, '') AS vendedor, "
                 "'ID de gestión' AS falta FROM regular g JOIN planes p ON p.id = g.plan_id "
                 "LEFT JOIN empleados e ON e.id = g.vendedor_id WHERE g.activo = 1 AND g.id_gestion = '' "
                 "ORDER BY g.fecha DESC, g.id DESC")


def _porta():
    filas = _rows("SELECT g.id, g.fecha, g.nombre, g.numero_portar AS numero, p.codigo AS plan, "
                  "COALESCE(e.nombre, '') AS vendedor, g.id_gestion, g.nim, g.pin, g.compania_donante, g.tipo_negocio "
                  "FROM porta g JOIN planes p ON p.id = g.plan_id LEFT JOIN empleados e ON e.id = g.vendedor_id "
                  "WHERE g.activo = 1 ORDER BY g.fecha DESC, g.id DESC")
    rotulos = (("id_gestion", "ID de gestión"), ("nim", "NIM"), ("pin", "PIN"), ("compania_donante", "compañía"),
               ("tipo_negocio", "tipo de negocio"))
    salida = []
    for f in filas:
        falta = [texto for campo, texto in rotulos if not f[campo]]
        if falta:
            salida.append({k: f[k] for k in ("id", "fecha", "nombre", "numero", "plan", "vendedor")}
                          | {"falta": ", ".join(falta)})
    return salida


def _casim():
    return _rows("SELECT g.id, g.fecha, g.nombre, g.numero, COALESCE(e.nombre, '') AS vendedor, "
                 "CASE WHEN g.numero = '' THEN 'sin número' ELSE length(g.numero) || ' dígitos en vez de 10' END AS falta "
                 "FROM casim g LEFT JOIN empleados e ON e.id = g.vendedor_id "
                 "WHERE g.activo = 1 AND (length(g.numero) <> 10 OR g.numero GLOB '*[^0-9]*') "
                 "ORDER BY g.fecha DESC, g.id DESC")


def _empleados():
    return _rows("SELECT e.id, e.nombre, e.rol, e.celular, 'sucursal' AS falta FROM empleados e WHERE e.activo = 1 "
                 "AND NOT EXISTS (SELECT 1 FROM empleado_sucursal es JOIN sucursales s ON s.id = es.sucursal_id "
                 "WHERE es.empleado_id = e.id AND s.activo = 1) ORDER BY e.nombre")


def _stock_negativo():
    return _rows("SELECT id, codigo, descripcion, stock FROM accesorios WHERE activo = 1 AND stock < 0 "
                 "ORDER BY stock, codigo")


def _equipos_sin_precio():
    return _rows("SELECT id, codigo, descripcion, marca, stock FROM equipos WHERE activo = 1 AND precio = 0 "
                 "ORDER BY marca, descripcion")


_FECHA = ("fecha", "Fecha", 130)
_QUE_FALTA = ("falta", "Qué falta", 220)

CATEGORIAS = (
    ("regular", "Regular sin ID de gestión", _regular,
     [_FECHA, ("nombre", "Nombre", 160), ("numero", "Número", 100), ("plan", "Plan", 70), ("vendedor", "Vendedor", 150), _QUE_FALTA]),
    ("porta", "Porta incompletas", _porta,
     [_FECHA, ("nombre", "Nombre", 160), ("numero", "Número a portar", 110), ("plan", "Plan", 80), ("vendedor", "Vendedor", 150), _QUE_FALTA]),
    ("casim", "CaSIM con número mal", _casim,
     [_FECHA, ("nombre", "Nombre", 160), ("numero", "Número", 130), ("vendedor", "Vendedor", 150), _QUE_FALTA]),
    ("empleados", "Empleados sin sucursal", _empleados,
     [("nombre", "Nombre", 220), ("rol", "Cargo", 130), ("celular", "Teléfono", 120), _QUE_FALTA]),
    ("stock", "Accesorios con stock negativo", _stock_negativo,
     [("codigo", "Código", 140), ("descripcion", "Descripción", 360), ("stock", "Stock", 80)]),
    ("equipos", "Equipos sin precio sugerido", _equipos_sin_precio,
     [("codigo", "Código", 120), ("descripcion", "Descripción", 320), ("marca", "Marca", 110), ("stock", "Stock", 70)]),
)


def categorias():
    """Todas las categorías con sus filas (las que no tienen nada pendiente quedan con la lista vacía)."""
    return [{"clave": clave, "titulo": titulo, "columnas": columnas, "filas": filas()}
            for clave, titulo, filas, columnas in CATEGORIAS]


def total():
    """Cuántos registros hay por completar en total, sin contar los equipos sin precio (es una carga, no un error)."""
    return sum(len(c["filas"]) for c in categorias() if c["clave"] != "equipos")
