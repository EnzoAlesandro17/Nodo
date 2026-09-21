"""Movimientos de stock: ingresos, ventas y conciliaciones de accesorios y equipos.

Cada movimiento modifica el stock del producto en la misma transacción que lo guarda:
  INGRESO       suma la cantidad
  VENTA         resta la cantidad
  CONCILIACION  ajuste por conteo: suma la cantidad, que puede ser negativa
Editar o dar de baja un movimiento revierte su efecto anterior. Los accesorios virtuales
(E-SIM) no llevan stock, así que sus movimientos no lo tocan.
"""
from db import imeis
from db.gestiones import GestionRepo
from models import MOV_ACCESORIOS, MOV_EQUIPOS

SIGNO = {"INGRESO": 1, "VENTA": -1, "CONCILIACION": 1}


def efecto(mov):
    """Cuánto suma (o resta, si es negativo) el movimiento al stock."""
    return SIGNO[mov["tipo"]] * mov["cantidad"]


class MovimientoRepo(GestionRepo):
    def __init__(self, table, fields, producto_table):
        super().__init__(table, fields, filter_key="tipo")
        self.producto_table = producto_table
        self.con_imei = any(f.key == "imei" for f in fields)   # las ventas de equipos llevan el IMEI de la unidad

    def check_imei(self, data, row_id=None):
        """Error si el IMEI de una venta no se puede tomar (cargado en otro modelo, o ya vendido en otra venta)."""
        imei = data.get("imei") if self.con_imei else ""
        if not imei or data["tipo"] != "VENTA":
            return None
        reg = imeis.buscar(imei)
        if reg is None:   # no está cargado: se vende igual, sin baja
            return None
        if reg["equipo_id"] != data["producto_id"]:
            return f"El IMEI {imei} está cargado en otro modelo: {reg['codigo']} - {reg['descripcion']}."
        if not reg["activo"] and reg["salida"] not in ("", f"{self.table}:{row_id}"):
            return f"El IMEI {imei} ya figura vendido en otra venta ({reg['salida']})."
        return None

    def _tomar_imei(self, row_id, data):
        if self.con_imei and data["tipo"] == "VENTA" and data.get("imei"):
            imeis.tomar(data["imei"], f"{self.table}:{row_id}")

    def _soltar_imei(self, row_id):
        if self.con_imei:
            imeis.soltar(f"{self.table}:{row_id}")

    def _sin_stock(self):
        """Condición SQL de los productos que no llevan stock (solo los accesorios virtuales)."""
        return "virtual = 1" if self.producto_table == "accesorios" else "0"

    def _sumar_stock(self, producto_id, cantidad):
        if cantidad:
            self._db.execute(f"UPDATE {self.producto_table} SET stock = stock + ? "
                             f"WHERE id = ? AND NOT ({self._sin_stock()})", (cantidad, producto_id))

    def stock_despues(self, data, anterior=None):
        """(stock hoy, stock resultante, sin_stock) si se guardara `data` en lugar de `anterior`."""
        hoy, sin_stock = self._db.execute(
            f"SELECT stock, {self._sin_stock()} FROM {self.producto_table} WHERE id = ?",
            (data["producto_id"],)).fetchone()
        resultado = hoy + efecto(data)
        if anterior and anterior["producto_id"] == data["producto_id"]:
            resultado -= efecto(anterior)
        return hoy, resultado, bool(sin_stock)

    # Variantes sin confirmar la transacción: las usan también las gestiones que generan una venta.
    def _insert_con_stock(self, data):
        row_id = self._insert_row(data)
        self._sumar_stock(data["producto_id"], efecto(data))
        self._tomar_imei(row_id, data)
        return row_id

    def _update_con_stock(self, row_id, data):
        anterior = self._get(row_id)
        self._sumar_stock(anterior["producto_id"], -efecto(anterior))
        self._soltar_imei(row_id)
        self._update_row(row_id, data)
        self._sumar_stock(data["producto_id"], efecto(data))
        self._tomar_imei(row_id, data)

    def _deactivate_con_stock(self, row_id):
        anterior = self._get(row_id)
        if anterior["activo"]:
            self._sumar_stock(anterior["producto_id"], -efecto(anterior))
            self._soltar_imei(row_id)
        self._db.execute("DELETE FROM pagos WHERE origen = ? AND mov_id = ?", (self.table, row_id))   # una baja no cuenta en caja
        self._deactivate_row(row_id)

    def insert(self, data):
        with self._db:
            return self._insert_con_stock(data)

    def update(self, row_id, data):
        with self._db:
            self._update_con_stock(row_id, data)

    def venta_id(self, row_id):
        """La venta de Nuevo > Accesorios a la que pertenece el movimiento, o None."""
        if self.table != "mov_accesorios":
            return None
        return self._db.execute("SELECT venta_id FROM mov_accesorios WHERE id = ?", (row_id,)).fetchone()[0]

    def deactivate(self, row_id):
        """Dar de baja un movimiento. Si es un producto de una venta con varios, se anula la venta entera:
        todos sus movimientos (con su stock) y sus pagos."""
        with self._db:
            venta_id = self.venta_id(row_id)
            if venta_id is None:
                return self._deactivate_con_stock(row_id)
            for (mov_id,) in self._db.execute("SELECT id FROM mov_accesorios WHERE venta_id = ?", (venta_id,)).fetchall():
                self._deactivate_con_stock(mov_id)
            self._db.execute("DELETE FROM pagos WHERE origen = 'ventas' AND mov_id = ?", (venta_id,))
            self._db.execute("UPDATE ventas SET activo = 0 WHERE id = ?", (venta_id,))


mov_accesorios = MovimientoRepo("mov_accesorios", MOV_ACCESORIOS, "accesorios")
mov_equipos = MovimientoRepo("mov_equipos", MOV_EQUIPOS, "equipos")
