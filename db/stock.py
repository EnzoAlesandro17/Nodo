"""Repositorios de las tablas de stock."""
from db import imeis
from db.repo import Repo
from models import ACCESORIOS, EQUIPOS


class EquipoRepo(Repo):
    """Equipos con la cantidad de IMEI cargados (`imeis`) y los días del más antiguo (`dias`)."""

    def list(self, search="", filter_value=None):
        rows = super().list(search, filter_value)
        resumen = imeis.resumen_por_equipo()
        for r in rows:
            r["imeis"], r["dias"] = resumen.get(r["id"], (0, 0))
        return rows


accesorios = Repo("accesorios", ACCESORIOS, filter_key="categoria")
equipos = EquipoRepo("equipos", EQUIPOS, filter_key="marca")
