"""Nuevo > Gasto: gastos simples (plata que sale de una cuenta)."""
from db import gestiones as repos
from ui.formatting import fmt_money
from ui.gestion_base import GestionScreen


class Gasto(GestionScreen):
    title = "Nuevo gasto"
    subtitle = "Gastos de la sucursal: se restan en la caja"
    repo = repos.gastos
    noun, noun_plural = "gasto", "gastos"
    form_new, form_edit = "Nuevo gasto", "Editar gasto"
    left_keys = ("detalle", "observaciones")
    item = "este gasto"

    def _defaults(self):
        """Sucursal, vendedor y cuenta del último gasto, para no elegirlos cada vez."""
        last = self.repo.list()[:1]
        return {k: last[0][k] for k in ("sucursal_id", "vendedor_id", "cuenta_id")} if last else {}

    def _validate(self, data):
        return None if data["monto"] > 0 else "El monto tiene que ser mayor a 0."

    def delete_prompt(self, row):
        return ("Dar de baja",
                f"¿Querés dar de baja {self.item}?\n\n    {row['detalle']} · {fmt_money(row['monto'])}\n\n"
                "Dejará de aparecer en el listado y en la caja.")
