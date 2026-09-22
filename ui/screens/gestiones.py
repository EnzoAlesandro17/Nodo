"""Pantallas del menú Nuevo > Gestiones."""
import re

from db import gestiones as repos
from ui.gestion_base import GestionScreen, GestionVentaScreen

SIM_FISICA = "7001335"   # USIM TRIO HALF CARD: la SIM que proponen Regular y Porta


class CaSIM(GestionVentaScreen):
    title = "Gestiones · CaSIM"
    subtitle = "Cambio de chip de un número"
    repo = repos.casim
    ref_filters = {"sim_id": "SIM"}   # el Tipo de SIM ofrece solo equipos marca SIM (no son un accesorio ni llevan IMEI)
    form_new, form_edit = "Nueva gestión CaSIM", "Editar gestión CaSIM"


class CaTER(GestionVentaScreen):
    title = "Gestiones · CaTER"
    subtitle = "Cambio de terminal de un número"
    repo = repos.cater
    form_new, form_edit = "Nueva gestión CaTER", "Editar gestión CaTER"


class Regular(GestionVentaScreen):
    title = "Gestiones · Regular"
    subtitle = "Alta de línea con plan regular"
    repo = repos.regular
    ref_filters = {"sim_id": "SIM"}
    sim_default = SIM_FISICA
    form_new, form_edit = "Nueva gestión Regular", "Editar gestión Regular"


class Porta(GestionVentaScreen):
    title = "Gestiones · Porta"
    subtitle = "Alta de línea con portabilidad"
    repo = repos.porta
    ref_filters = {"sim_id": "SIM"}
    sim_default = SIM_FISICA
    number_key = "numero_portar"
    form_new, form_edit = "Nueva gestión Porta", "Editar gestión Porta"


class BAF(GestionScreen):
    title = "Gestiones · BAF"
    subtitle = "Venta e instalación de fibra óptica"
    repo = repos.baf
    number_key = "telefono"
    form_columns = 2
    left_keys = ("nombre",)
    form_new, form_edit = "Nueva gestión BAF", "Editar gestión BAF"

    # En la tabla, este orden (no el del formulario, agrupado por sección: ver models.BAF).
    _COLUMNAS_TABLA = ("fecha", "nombre", "plan_id", "estado", "fecha_pactada", "fecha_instalacion")

    @property
    def columns(self):
        por_clave = {f.key: f for f in self.fields}
        return [por_clave[k] for k in self._COLUMNAS_TABLA]

    def _validate(self, data):
        estado = data["estado"]
        ingreso, pactada, instalacion = data["fecha"][:10], data["fecha_pactada"], data["fecha_instalacion"]
        if data["email"] and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", data["email"]):
            return "Mail: no parece una dirección válida."
        if estado in ("Pactada", "Instalada") and not pactada:
            return "La fecha pactada es obligatoria si el estado es Pactada o Instalada."
        if estado == "Instalada":
            for key, label in (("fecha_instalacion", "La fecha de instalación"), ("ot", "El código de OT"),
                               ("sds", "El código de SDS")):
                if not data[key]:
                    return f"{label} es obligatorio si el estado es Instalada."
        if pactada and pactada < ingreso:
            return "La fecha pactada tiene que ser igual o posterior a la de ingreso."
        if instalacion and pactada and instalacion < pactada:
            return "La fecha de instalación tiene que ser igual o posterior a la pactada."
        return None
