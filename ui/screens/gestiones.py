"""Pantallas del menú Nuevo > Gestiones."""
import re
import webbrowser
from tkinter import messagebox, simpledialog, ttk

from db import formulario_baf
from db import gestiones as repos
from models import CATEGORIA_BAF, CATEGORIA_LINEAS
from ui import theme
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
    ref_filters = {"sim_id": "SIM", "plan_id": CATEGORIA_LINEAS}   # Plan: solo los de líneas
    form_columns = 2   # formulario en dos columnas, por secciones (ver models._linea)
    orden_columnas = ("fecha", "nombre", "numero", "plan_id", "id_gestion", "vendedor_id", "observaciones")
    sim_default = SIM_FISICA
    form_new, form_edit = "Nueva gestión Regular", "Editar gestión Regular"


class Porta(GestionVentaScreen):
    title = "Gestiones · Porta"
    subtitle = "Alta de línea con portabilidad"
    repo = repos.porta
    ref_filters = {"sim_id": "SIM", "plan_id": CATEGORIA_LINEAS}
    form_columns = 2
    orden_columnas = ("fecha", "nombre", "numero_portar", "plan_id", "id_gestion", "vendedor_id", "fecha_portacion",
                      "estado", "observaciones")
    sim_default = SIM_FISICA
    number_key = "numero_portar"
    form_new, form_edit = "Nueva gestión Porta", "Editar gestión Porta"


class BAF(GestionScreen):
    title = "Gestiones · BAF"
    subtitle = "Venta e instalación de fibra óptica"
    repo = repos.baf
    ref_filters = {"plan_id": CATEGORIA_BAF}   # Plan de internet: solo los de fibra
    number_key = "telefono"
    form_columns = 2
    left_keys = ("nombre",)
    form_new, form_edit = "Nueva gestión BAF", "Editar gestión BAF"

    # En la tabla, este orden (no el del formulario, agrupado por sección: ver models.BAF).
    orden_columnas = ("fecha", "nombre", "plan_id", "ot", "sds", "vendedor_id", "estado", "fecha_pactada",
                      "fecha_instalacion")

    # Fondo de cada fila según el estado: Instalada en verde, Cancelada en rojo y el resto (en curso) en amarillo
    zebra = False

    def build(self, card):
        super().build(card)
        for tag, color in (("instalada", theme.FILA_OK), ("cancelada", theme.FILA_MAL),
                           ("en_curso", theme.FILA_PENDIENTE)):
            self.tree.tag_configure(tag, background=color)

    def _display(self, field, row):
        if field.key == "plan_id":   # solo el nombre clave: «200MB + TV HD» (la descripción no entra)
            return (row.get("plan_id_label") or "").split(" - ")[0]
        return super()._display(field, row)

    def row_tags(self, row):
        return ({"Instalada": "instalada", "Cancelada": "cancelada"}.get(row["estado"], "en_curso"),)

    # --- formulario de Google (ver db/formulario_baf.py) ---------------
    def extra_actions(self, bar):
        self.btn_form = ttk.Button(bar, text="Cargar en el formulario", command=self.cargar_formulario)
        self.btn_form.pack(side="left", padx=(16, 0))
        ttk.Button(bar, text="Link del formulario", command=self.pedir_link).pack(side="left", padx=(8, 0))

    def _update_buttons(self):
        super()._update_buttons()
        if hasattr(self, "btn_form"):
            self.btn_form.config(state=self.btn_edit.cget("state"))

    def pedir_link(self):
        """Pide el link del formulario (cambia cada mes). Devuelve el link, o "" si se canceló."""
        link = simpledialog.askstring("Link del formulario",
                                      "Pegá el link del formulario de Google de las BAF (el de este mes):",
                                      initialvalue=formulario_baf.link_guardado(), parent=self.winfo_toplevel())
        if link and link.strip():
            formulario_baf.guardar_link(link)
            return link.strip()
        return ""

    def cargar_formulario(self):
        """Abre el formulario en el navegador con los datos de la gestión elegida, para revisarlo y enviarlo."""
        row_id = self._selected_id()
        if row_id is None:
            return
        row, parent = self.rows[row_id], self.winfo_toplevel()
        link = formulario_baf.link_guardado() or self.pedir_link()
        if not link:
            return
        parent.config(cursor="watch")
        parent.update_idletasks()
        try:
            url, avisos = formulario_baf.link_precargado(link, formulario_baf.preguntas(link), row)
        except formulario_baf.FormularioError as e:
            messagebox.showerror("Formulario", str(e), parent=parent)
            return
        finally:
            parent.config(cursor="")
        webbrowser.open(url)
        aviso = ("Se abrió el formulario con los datos precargados. Revisalo, completá lo que falte y envialo.\n\n"
                 "Quedan para completar a mano: Acometimientos y las de portabilidad. Y tildá "
                 "«Enviarme una copia de mis respuestas».")
        for texto in avisos:
            aviso += "\n\n" + texto
        if row["con_form"]:
            messagebox.showinfo("Formulario", aviso + "\n\nEsta gestión ya estaba marcada como cargada.", parent=parent)
        elif messagebox.askyesno("Formulario", aviso + "\n\nCuando lo envíes: ¿la marco como cargada en el formulario?",
                                 parent=parent):
            self.repo.update_fields(row_id, {"con_form": 1})
            self.reload(select=row_id)

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
