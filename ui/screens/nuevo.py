"""Pantallas del menú Nuevo (carga de ventas)."""
from ui.base import Screen


class Transfer(Screen):
    title = "Nueva transferencia"
    subtitle = "Transferencia entre cuentas"


class Conciliacion(Screen):
    title = "Conciliación"
    subtitle = "Conciliación de movimientos"


class Consultas(Screen):
    title = "Consultas"
    subtitle = "Búsqueda y consulta de ventas cargadas"
    actions = ("Buscar",)
