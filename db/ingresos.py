"""Ingreso de equipos con remito: una lista de IMEI con su modelo, todos a una sucursal.

Guarda los IMEI y suma el stock con un INGRESO por modelo, todo en la misma transacción.
"""
from datetime import datetime

from db import connection, imeis, movimientos


def ultima_sucursal():
    """El id de la sucursal del último IMEI cargado (para proponerla en el próximo ingreso), o None."""
    row = connection.get().execute("SELECT sucursal_id FROM imeis ORDER BY id DESC LIMIT 1").fetchone()
    return row[0] if row else None


def registrar(pedido, sucursal_id, fecha, items):
    """`items`: [(imei, equipo_id)]; `fecha`: "AAAA-MM-DD". ValueError (con el motivo) si algún IMEI se repite o ya
    está cargado: en ese caso no se guarda nada. Devuelve la cantidad de modelos distintos."""
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
    return len(por_modelo)
