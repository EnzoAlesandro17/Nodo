"""Pantallas del menú Administración."""
import re

from db import administracion as repos
from ui.codigo_base import CodigoScreen
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
    left_keys = ("nombre",)

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
