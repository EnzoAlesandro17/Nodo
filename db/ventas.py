"""Venta de accesorios con varios productos y pagos combinados (Nuevo > Accesorios).

Cada producto genera un movimiento VENTA en mov_accesorios (descuenta stock, con `venta_id`) y los pagos
van a la tabla `pagos` con origen = 'ventas'. Todo se guarda en una sola transacción.
Para anular una venta se da de baja cualquiera de sus movimientos (ver MovimientoRepo.deactivate).
"""
from db import connection
from db.movimientos import mov_accesorios


def ultimos_datos():
    """(sucursal_id, vendedor_id) de la última venta de accesorios, para no elegirlos cada vez."""
    db = connection.get()
    row = db.execute("SELECT sucursal_id, vendedor_id FROM ventas WHERE activo = 1 ORDER BY id DESC LIMIT 1").fetchone() \
        or db.execute("SELECT sucursal_id, vendedor_id FROM mov_accesorios WHERE activo = 1 AND tipo = 'VENTA' "
                      "ORDER BY id DESC LIMIT 1").fetchone()
    return (row[0], row[1]) if row else (None, None)


def faltantes(items):
    """Productos que quedarían con stock negativo: [(código - descripción, stock hoy, stock que quedaría)].
    `items`: [(producto_id, cantidad, precio)]. Los virtuales (E-SIM) no llevan stock."""
    pedido = {}
    for producto_id, cantidad, _ in items:
        pedido[producto_id] = pedido.get(producto_id, 0) + cantidad
    out = []
    for producto_id, cantidad in pedido.items():
        codigo, descripcion, hoy, virtual = connection.get().execute(
            "SELECT codigo, descripcion, stock, virtual FROM accesorios WHERE id = ?", (producto_id,)).fetchone()
        if not virtual and hoy - cantidad < 0:
            out.append((f"{codigo} - {descripcion}", hoy, hoy - cantidad))
    return out


def registrar(cab, items, pagos):
    """Guarda la venta y devuelve su id.

    `cab`: fecha ("AAAA-MM-DD HH:MM:SS"), cliente, vendedor_id, sucursal_id, cupon, factura.
    `items`: [(producto_id, cantidad, precio unitario)].
    `pagos`: [(cuenta_id, monto, interes)]: `monto` es la parte de la venta que cubre el pago e `interes`
    lo que el posnet cobró de más; los `monto` tienen que sumar el total de la venta.
    ValueError (con el motivo) si algo no cierra: en ese caso no se guarda nada.
    """
    if not items:
        raise ValueError("La venta no tiene productos.")
    if any(cantidad <= 0 or precio < 0 for _, cantidad, precio in items):
        raise ValueError("Las cantidades tienen que ser mayores a 0 y los precios no pueden ser negativos.")
    if not pagos:
        raise ValueError("Falta cargar al menos un pago.")
    if any(monto <= 0 or interes < 0 for _, monto, interes in pagos):
        raise ValueError("Los montos de los pagos tienen que ser mayores a 0 y los intereses no pueden ser negativos.")
    total = round(sum(cantidad * precio for _, cantidad, precio in items), 2)
    pagado = round(sum(monto for _, monto, _ in pagos), 2)
    if pagado != total:
        raise ValueError(f"Los pagos suman {pagado:.2f} y la venta es de {total:.2f}.")

    db = connection.get()
    cuentas = {cuenta_id for cuenta_id, _, _ in pagos}
    with db:
        medio = ""   # con una sola cuenta, su código; con varias, el detalle está en `pagos`
        if len(cuentas) == 1:
            medio = db.execute("SELECT codigo FROM cuentas WHERE id = ?", (next(iter(cuentas)),)).fetchone()[0]
        venta_id = db.execute(
            "INSERT INTO ventas (fecha, cliente, vendedor_id, sucursal_id, cupon, factura) VALUES (?, ?, ?, ?, ?, ?)",
            (cab["fecha"], cab["cliente"], cab["vendedor_id"], cab["sucursal_id"], cab["cupon"], cab["factura"])
        ).lastrowid
        for producto_id, cantidad, precio in items:
            mov_id = mov_accesorios._insert_con_stock({
                "fecha": cab["fecha"], "tipo": "VENTA", "producto_id": producto_id, "cantidad": cantidad,
                "precio": precio, "cliente": cab["cliente"], "medio": medio, "vendedor_id": cab["vendedor_id"],
                "sucursal_id": cab["sucursal_id"], "cupon": cab["cupon"], "factura": cab["factura"],
                "observaciones": f"VENTA {venta_id}"})
            db.execute("UPDATE mov_accesorios SET venta_id = ? WHERE id = ?", (venta_id, mov_id))
        db.executemany("INSERT INTO pagos (origen, mov_id, cuenta_id, monto, interes) VALUES ('ventas', ?, ?, ?, ?)",
                       [(venta_id, cuenta_id, monto, interes) for cuenta_id, monto, interes in pagos])
    return venta_id
