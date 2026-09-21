"""Pantalla genérica de gestiones: tabla con alta / edición / baja (CRUD) de trámites."""
from tkinter import messagebox

from db import refs, stock
from ui.formatting import fmt_money
from ui.table_base import TableScreen


class GestionScreen(TableScreen):
    """Subclases: `repo` (db.gestiones.GestionRepo), textos y, si hace falta, `ref_filters`."""
    noun, noun_plural = "gestión", "gestiones"
    default_sort, default_desc = "fecha", True   # la más reciente primero
    left_keys = ("nombre", "observaciones")
    ref_filters = {}          # {campo select: valor de filtro}, p. ej. {"sim_id": "SIMS"} = solo esa categoría
    item = "esta gestión"     # para el aviso de baja
    number_key = "numero"     # el número que identifica la gestión en el aviso de baja

    # --- formulario ----------------------------------------------------
    def _choices(self):
        choices = super()._choices()
        for f in self.fields:
            if f.kind in ("select", "multi"):
                choices[f.key] = refs.choices(f.ref, self.ref_filters.get(f.key))
            elif f.kind == "pagos":
                choices[f.key] = refs.codigos(f.ref)
        return choices

    def _confirm_stock(self, data, anterior=None):
        """Avisa si guardar dejaría el stock en negativo (repos con `stock_despues`).
        Devuelve un error, o None si se sigue."""
        hoy, resultado, sin_stock = self.repo.stock_despues(data, anterior)
        if sin_stock or resultado >= 0 or resultado >= hoy:
            return None
        if messagebox.askyesno("Stock insuficiente",
                               f"El stock de este producto pasaría de {hoy} a {resultado}.\n\n"
                               "¿Registrar igual?", icon="warning", parent=self.winfo_toplevel()):
            return None
        return f"El stock quedaría en {resultado}."

    def _suggestions(self):
        return {f.key: (f.suggests, refs.prices(f.ref)) for f in self.fields if f.suggests}

    def _validate(self, data):
        """Reglas propias de cada gestión, además de las de los campos. Devuelve un error, o None."""
        return None

    def _save_new(self, data, dialog):
        error = self._validate(data)
        if error:
            return error
        self.reload(select=self.repo.insert(data))

    def _save_edit(self, row_id, data):
        error = self._validate(data)
        if error:
            return error
        self.repo.update(row_id, data)
        self.reload(select=row_id)

    def delete_prompt(self, row):
        monto = f" · {fmt_money(row['monto'])}" if "monto" in row else ""
        return ("Dar de baja",
                f"¿Querés dar de baja {self.item}?\n\n    {row['nombre']} · {row[self.number_key]}{monto}\n\n"
                "Dejará de aparecer en el listado.")


class GestionVentaScreen(GestionScreen):
    """Gestión que vende un producto del stock (repo: db.gestiones.GestionVentaRepo)."""

    sim_default = ""   # código del accesorio que se propone como Tipo de SIM (Regular y Porta), si la gestión lo tiene

    def _defaults(self):
        """Sucursal y vendedor de la última gestión (y su SIM, si la gestión la pide), para no elegirlos cada vez."""
        last = self.repo.list()[:1]
        keys = ("sucursal_id", "vendedor_id") + (("sim_id",) if self.sim_default else ())
        defaults = {k: last[0][k] for k in keys if last and last[0].get(k) is not None}
        if self.sim_default and "sim_id" not in defaults:
            sim = stock.accesorios.get_by_codigo(self.sim_default)
            if sim and sim["activo"]:
                defaults["sim_id"] = sim["id"]
        return defaults

    def _check_pagos(self, data):
        """Avisa si los pagos cargados no suman el monto. Devuelve un error, o None si se sigue."""
        pagos = data.get("pagos")
        pagado = round(sum(monto for _, monto in pagos or []), 2)
        if not pagos or pagado == data["monto"]:
            return None
        if messagebox.askyesno("Pagos",
                               f"Los pagos suman {fmt_money(pagado)} y el monto es {fmt_money(data['monto'])}.\n\n"
                               "¿Guardar igual?", icon="warning", parent=self.winfo_toplevel()):
            return None
        return "Los pagos no coinciden con el monto."

    def _save_new(self, data, dialog):
        return (self.repo.check_imei(data) or self._check_pagos(data) or self._confirm_stock(data)
                or super()._save_new(data, dialog))

    def _save_edit(self, row_id, data):
        return (self.repo.check_imei(data, self.rows[row_id]) or self._check_pagos(data)
                or self._confirm_stock(data, self.rows[row_id]) or super()._save_edit(row_id, data))

    def delete_prompt(self, row):
        title, message = super().delete_prompt(row)
        return title, message + "\nSe devuelve el producto al stock."
