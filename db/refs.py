"""Cómo se muestran (y se ofrecen en las listas) los registros a los que apuntan los campos `select`."""

# tabla -> campos que forman el texto, unidos con « - » (p. ej. «7001374 - E-SIM»)
LABEL_FIELDS = {
    "accesorios": ("codigo", "descripcion"),
    "equipos": ("codigo", "descripcion"),
    "cuentas": ("codigo", "descripcion"),
    "areas": ("codigo", "nombre"),
    "sucursales": ("codigo", "nombre"),
    "empleados": ("nombre",),
    "planes": ("codigo", "descripcion"),
    "descuentos": ("codigo", "descripcion"),
}


# tabla -> campo con el precio que se propone al elegir un registro (ver Field.suggests)
PRICE_FIELD = {"equipos": "precio"}


def _repo(ref):
    from db import administracion, stock   # acá para evitar importaciones circulares
    return {"accesorios": stock.accesorios, "equipos": stock.equipos, "cuentas": administracion.cuentas,
            "areas": administracion.areas, "sucursales": administracion.sucursales, "empleados": administracion.empleados,
            "planes": administracion.planes, "descuentos": administracion.descuentos}[ref]


def codigos(ref):
    """[(id, código)] de los registros activos de `ref` (que tenga campo `codigo`)."""
    return [(r["id"], r["codigo"]) for r in _repo(ref).list()]


def prices(ref):
    """{id: precio sugerido} de los registros activos de `ref`."""
    key = PRICE_FIELD[ref]
    return {r["id"]: r[key] for r in _repo(ref).list()}


def label_sql(ref, alias):
    """Expresión SQL del texto de un registro de `ref` (tabla con alias `alias`)."""
    return " || ' - ' || ".join(f"{alias}.{f}" for f in LABEL_FIELDS[ref])


def search_columns(ref, alias):
    return [f"{alias}.{f}" for f in LABEL_FIELDS[ref]]


def choices(ref, filter_value=None):
    """Opciones activas de `ref` como [(id, texto)]. `filter_value` filtra por el campo de filtro del repo."""
    return [(r["id"], " - ".join(str(r[f]) for f in LABEL_FIELDS[ref]))
            for r in _repo(ref).list("", filter_value)]
