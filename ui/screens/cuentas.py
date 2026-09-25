"""Pantalla de cuentas: efectivo, bancos, terminales de cobro y sus subcuentas."""
from db import administracion as repos
from ui.codigo_base import CodigoScreen


class Cuentas(CodigoScreen):
    title = "Cuentas"
    subtitle = "Efectivo, bancos y terminales de cobro, con sus subcuentas (GETNET > GETNET VISA...)"
    repo = repos.cuentas
    noun, noun_plural = "cuenta", "cuentas"
    form_new, form_edit = "Nueva cuenta", "Editar cuenta"
    fem = True

    def _choices(self):
        choices = super()._choices()
        # la cuenta padre: una que no sea subcuenta de otra (dos niveles)
        choices["padre_id"] = [(r["id"], f"{r['codigo']} - {r['descripcion']}")
                               for r in self.repo.list() if not r["padre_id"]]
        return choices

    def _save_new(self, data, dialog):
        return self.repo.check_padre(None, data["padre_id"]) or super()._save_new(data, dialog)

    def _save_edit(self, row_id, data):
        return self.repo.check_padre(row_id, data["padre_id"]) or super()._save_edit(row_id, data)
