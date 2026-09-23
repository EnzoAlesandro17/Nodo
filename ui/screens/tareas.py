"""Administración > Tareas: pendientes del local (traídas de MyTools)."""
from datetime import date

from db import gestiones as repos
from ui.gestion_base import GestionScreen


class Tareas(GestionScreen):
    title = "Administración · Tareas"
    subtitle = "Pendientes del local: en rojo las abiertas prioritarias o con la fecha límite vencida"
    repo = repos.tareas
    noun, noun_plural = "tarea", "tareas"
    form_new, form_edit = "Nueva tarea", "Editar tarea"
    left_keys = ("titulo",)
    item = "esta tarea"

    def row_tags(self, row):
        vencida = row["fecha_limite"] and row["fecha_limite"] < date.today().isoformat()
        return ("viejo",) if row["estado"] == "Abierta" and (row["prioritaria"] or vencida) else ()

    def delete_prompt(self, row):
        return ("Dar de baja",
                f"¿Querés dar de baja {self.item}?\n\n    {row['titulo']}\n\nDejará de aparecer en el listado.")
