"""Pantalla de cuentas: efectivo, bancos y cuentas en general."""
from db import administracion as repos
from ui.codigo_base import CodigoScreen


class Cuentas(CodigoScreen):
    title = "Cuentas"
    subtitle = "Efectivo, bancos y cuentas en general"
    repo = repos.cuentas
    noun, noun_plural = "cuenta", "cuentas"
    form_new, form_edit = "Nueva cuenta", "Editar cuenta"
    fem = True
