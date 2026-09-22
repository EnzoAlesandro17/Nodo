"""Pantallas del menú Administración."""
import re

from db import administracion as repos
from ui.codigo_base import CodigoScreen
from ui.formatting import fmt_date
from ui.table_base import TableScreen


class Sucursales(CodigoScreen):
    title = "Administración · Sucursales"
    subtitle = "Alta y edición de sucursales"
    repo = repos.sucursales
    noun, noun_plural = "sucursal", "sucursales"
    form_new, form_edit = "Nueva sucursal", "Editar sucursal"
    fem = True
    label_key = "nombre"
    default_sort = "codigo"
    left_keys = ("nombre",)


class Empleados(TableScreen):
    title = "Administración · Empleados"
    subtitle = "Alta y edición de empleados, asignados a una o varias sucursales"
    repo = repos.empleados
    noun, noun_plural = "empleado", "empleados"
    form_new, form_edit = "Nuevo empleado", "Editar empleado"
    default_sort = "nombre"
    left_keys = ("nombre", "email")

    def _choices(self):
        choices = super()._choices()
        choices["sucursales"] = [(r["id"], f"{r['codigo']} - {r['nombre']}") for r in repos.sucursales.list()]
        return choices

    def _save_new(self, data, dialog):
        self.reload(select=self.repo.insert(data))

    def _save_edit(self, row_id, data):
        self.repo.update(row_id, data)
        self.reload(select=row_id)

    def delete_prompt(self, row):
        return ("Dar de baja",
                f"¿Querés dar de baja a este empleado?\n\n    {row['nombre']}\n\n"
                "Dejará de aparecer en el listado.")


class Planes(CodigoScreen):
    title = "Administración · Planes"
    subtitle = "Planes vigentes que se ofrecen en las gestiones"
    repo = repos.planes
    noun, noun_plural = "plan", "planes"
    form_new, form_edit = "Nuevo plan", "Editar plan"

    def sort_value(self, row, key):
        if key == "codigo":   # 2GB antes que 10GB
            return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", row[key])]
        return super().sort_value(row, key)


class PlanesBaf(Planes):
    title = "Administración · Planes BAF"
    subtitle = "Planes de fibra vigentes que se ofrecen en BAF"
    repo = repos.planes_baf


class Descuentos(CodigoScreen):
    title = "Administración · Descuentos"
    subtitle = "Descuentos que se ofrecen en las gestiones"
    repo = repos.descuentos
    noun, noun_plural = "descuento", "descuentos"
    form_new, form_edit = "Nuevo descuento", "Editar descuento"


class Cierres(TableScreen):
    title = "Administración · Días cerrados"
    subtitle = "Feriados y otros días que el local no abre: se cargan año a año, y Estadísticas los usa para la proyección del mes"
    repo = repos.cierres
    noun, noun_plural = "día cerrado", "días cerrados"
    form_new, form_edit = "Nuevo día cerrado", "Editar día cerrado"
    default_sort, default_desc = "fecha", False
    left_keys = ("motivo",)

    def _repetido(self, fecha, row_id=None):
        return next((r for r in self.repo.list() if r["fecha"] == fecha and r["id"] != row_id), None)

    def _save_new(self, data, dialog):
        if self._repetido(data["fecha"]):
            return f"Ya hay un día cerrado cargado para el {fmt_date(data['fecha'])}."
        self.reload(select=self.repo.insert(data))

    def _save_edit(self, row_id, data):
        if self._repetido(data["fecha"], row_id):
            return f"Ya hay un día cerrado cargado para el {fmt_date(data['fecha'])}."
        self.repo.update(row_id, data)
        self.reload(select=row_id)

    def delete_prompt(self, row):
        return ("Quitar de la lista", f"¿Querés quitar el {fmt_date(row['fecha'])} de los días cerrados?")
