"""Ingreso de equipos con remito: una lista de IMEI con su modelo, todos a una sucursal.

Guarda los IMEI y suma el stock con un INGRESO por modelo, todo en la misma transacción. Claro manda los chips
en el mismo pedido que los equipos, pero sin un número de serie que valga la pena cargar (la sucursal no los
entrega en orden, así que no hay IMEI que llevarles): van aparte, como `chips`, solo por cantidad (son un
equipo más, marca "SIM", así que su movimiento también es un INGRESO de mov_equipos, sin IMEI).
"""
from datetime import datetime

from db import connection, imeis, movimientos


def ultima_sucursal():
    """El id de la sucursal del último IMEI cargado (para proponerla en el próximo ingreso), o None."""
    row = connection.get().execute("SELECT sucursal_id FROM imeis ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def registrar(pedido, sucursal_id, fecha, items, chips=()):
    """`items`: [(imei, equipo_id)]; `chips`: [(equipo_id del chip, cantidad)]; `fecha`: "AAAA-MM-DD". ValueError
    (con el motivo) si algún IMEI se repite o ya está cargado: en ese caso no se guarda nada. Devuelve (modelos
    de equipos distintos, chips cargados)."""
    vistos = set()
    for imei, _ in items:
        if imei in vistos:
            raise ValueError(f"El IMEI {imei} está repetido en la lista.")
        vistos.add(imei)
        reg = imeis.buscar(imei)
        if reg and reg["activo"]:
            raise ValueError(f"El IMEI {imei} ya está cargado en {reg['codigo']} - {reg['descripcion']}.")
    por_modelo = {}
    for imei, equipo_id in items:
        por_modelo.setdefault(equipo_id, []).append(imei)
    hora = datetime.now().strftime("%H:%M:%S")
    db = connection.get()
    with db:
        for imei, equipo_id in items:
            imeis._guardar(db, equipo_id, imei, sucursal_id, fecha, pedido)
        for equipo_id, lista in por_modelo.items():
            movimientos.mov_equipos._insert_con_stock({
                "fecha": f"{fecha} {hora}", "tipo": "INGRESO", "producto_id": equipo_id, "cantidad": len(lista),
                "precio": 0.0, "cliente": "", "medio": "", "vendedor_id": None, "sucursal_id": sucursal_id,
                "cupon": "", "factura": "", "observaciones": f"PEDIDO {pedido} · {len(lista)} IMEI", "imei": ""})
        for equipo_id, cantidad in chips:
            movimientos.mov_equipos._insert_con_stock({
                "fecha": f"{fecha} {hora}", "tipo": "INGRESO", "producto_id": equipo_id, "cantidad": cantidad,
                "precio": 0.0, "cliente": "", "medio": "", "vendedor_id": None, "sucursal_id": sucursal_id,
                "cupon": "", "factura": "", "observaciones": f"PEDIDO {pedido}", "imei": ""})
    return len(por_modelo), len(chips)
