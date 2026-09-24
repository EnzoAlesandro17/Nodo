"""Pantallas del menú Administrar."""
import re

from db import administracion as repos, refs
from ui.codigo_base import CodigoScreen
from ui.table_base import TableScreen


class Areas(CodigoScreen):
    title = "Administrar · Áreas"
    subtitle = "Áreas que agrupan las sucursales: cada sucursal pertenece a un área"
    repo = repos.areas
    noun, noun_plural = "área", "áreas"
    form_new, form_edit = "Nueva área", "Editar área"
    fem = True
    label_key = "nombre"
    left_keys = ("nombre",)

    @property
    def _g(self):
        return super()._g | {"un": "un"}   # «un área», como «el área», aunque sea femenino

    def delete_prompt(self, row):
        title, message = super().delete_prompt(row)
        n = repos.sucursales.contar_por_area(row["id"])
        if n:
            message += (f"\n\nTiene {n} sucursal{'' if n == 1 else 'es'} activa{'' if n == 1 else 's'}: "
                        f"sigue{'' if n == 1 else 'n'} en esta área hasta que le{'' if n == 1 else 's'} asignes otra.")
        return title, message


class Sucursales(CodigoScreen):
    title = "Administrar · Sucursales"
    subtitle = "Alta y edición de sucursales, cada una dentro de un área"
    repo = repos.sucursales
    noun, noun_plural = "sucursal", "sucursales"
    form_new, form_edit = "Nueva sucursal", "Editar sucursal"
    fem = True
    label_key = "nombre"
    default_sort = "codigo"
    left_keys = ("nombre",)

    def _choices(self):
        choices = super()._choices()
        choices["area_id"] = refs.choices("areas")
        return choices


class Empleados(TableScreen):
    title = "Administrar · Empleados"
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
    title = "Administrar · Planes"
    subtitle = "Planes vigentes que se ofrecen en las gestiones: los de LÍNEAS en Regular y Porta, los de BAF en BAF"
    repo = repos.planes
    noun, noun_plural = "plan", "planes"
    form_new, form_edit = "Nuevo plan", "Editar plan"

    def sort_value(self, row, key):
        if key == "codigo":   # 2GB antes que 10GB
            return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", row[key])]
        return super().sort_value(row, key)


class Descuentos(CodigoScreen):
    title = "Administrar · Descuentos"
    subtitle = "Descuentos que se ofrecen en las gestiones"
    repo = repos.descuentos
    noun, noun_plural = "descuento", "descuentos"
    form_new, form_edit = "Nuevo descuento", "Editar descuento"

