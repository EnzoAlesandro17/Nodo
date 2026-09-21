"""Pantalla de tabla para registros con código único (productos, sucursales, cuentas).

Alta, edición y baja lógica: un código no puede repetirse, y si el código ya existe
pero está dado de baja, se ofrece reactivarlo.
"""
from tkinter import messagebox

from ui.table_base import TableScreen


class CodigoScreen(TableScreen):
    fem = False              # el sustantivo es femenino (una sucursal, una cuenta)
    label_key = "descripcion"  # campo que acompaña al código en los avisos

    # --- textos con género ---------------------------------------------
    @property
    def _g(self):
        f = self.fem
        return {
            "un": "una" if f else "un", "este": "esta" if f else "este",
            "activo": "activa" if f else "activo", "baja": "dada de baja" if f else "dado de baja",
            "nuevo": "nueva" if f else "nuevo", "lo": "la" if f else "lo",
        }

    def _label(self, row):
        return f"{row['codigo']} - {row[self.label_key]}"

    # --- alta / edición / baja -----------------------------------------
    def _save_new(self, data, dialog):
        g, noun = self._g, self.noun
        existing = self.repo.get_by_codigo(data["codigo"])
        if existing is None:
            row_id = self.repo.insert(data)
        elif existing["activo"]:
            return f"Ya existe {g['un']} {noun} {g['activo']} con el código {data['codigo']}."
        else:
            reactivate = messagebox.askyesno(
                f"{noun.capitalize()} {g['baja']}",
                f"Existe {g['un']} {noun} {g['baja']} con el código {data['codigo']}:\n\n"
                f"    {self._label(existing)}\n\n"
                f"¿Querés reactivar{g['lo']}? Se reactivará con los datos que cargaste.",
                parent=dialog)
            if not reactivate:
                return f"Usá otro código para cargar {g['un']} {noun} {g['nuevo']}."
            row_id = existing["id"]
            self.repo.reactivate(row_id, data)
        self.reload(select=row_id)

    def _save_edit(self, row_id, data):
        g = self._g
        other = self.repo.get_by_codigo(data["codigo"])
        if other and other["id"] != row_id:
            estado = f"{g['un']} {self.noun} " + (g["activo"] if other["activo"] else g["baja"])
            return f"Ya existe {estado} con el código {data['codigo']}."
        self.repo.update(row_id, data)
        self.reload(select=row_id)

    def delete_prompt(self, row):
        g = self._g
        return ("Dar de baja",
                f"¿Querés dar de baja {g['este']} {self.noun}?\n\n    {self._label(row)}\n\n"
                "Dejará de aparecer en el listado, pero no se pierde: si más adelante cargás "
                f"{g['un']} {self.noun} con el mismo código, se te ofrecerá reactivar{g['lo']}.")
