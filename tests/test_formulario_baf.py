"""Precarga del formulario de Google de las BAF: qué respuesta va en cada pregunta (sin conectarse a internet)."""
import unittest
from urllib.parse import parse_qs, urlparse

from db import formulario_baf

LINK = "https://docs.google.com/forms/d/e/ABC123/viewform?usp=sf_link"

# como las devuelve formulario_baf.preguntas (títulos normalizados)
PREGUNTAS = {
    "MODO": (1, ["Timbreo", "Whatsapp", "Local"]),
    "VENDEDOR": (2, ["FLORENCIA BRUSUTTI", "ENZO AMADORI"]),
    "LOCALIDAD": (3, ["Rosario", "San Nicolas", "Corrientes"]),
    "CALLE": (4, []),
    "ALTURA": (5, []),
    "PISO Y DEPTO NUMERO DE TIRA TORRE O MONOBLOCK SI CORRESPNDE": (6, []),
    "ENTRE CALLES": (18, []),
    "INMUEBLE": (7, ["Casa", "Empresa", "Pasillo", "Edificio"]),
    "NOMBRE Y APELLIDO": (8, []),
    "TIPO DOC": (9, ["DNI", "LC", "LE", "Extranjero", "CUIT"]),
    "NRO DOCUMENTO": (10, []),
    "FECHA NAC": (11, []),
    "TELEFONO": (12, []),
    "TELEFONO ALTERNATIVO": (13, []),
    "MAIL": (19, []),
    "SERVICIO": (14, ["Duo", "Triple", "Duo CUIT", "Triple CUIT", "Añadir TV"]),
    "PLAN": (15, ["200 MB", "500 MB", "800 MB", "200 MB + TV", "500 MB + TV", "800 MB + TV"]),
    "DECOS": (16, ["1", "2", "3"]),
    "ESTADO": (21, ["Solicitud de preventa", "No le interesa el servicio", "No contesta"]),
    "OBSERVACIONES": (17, []),
}


def gestion(**cambios):
    row = {"vendedor_id_label": "AMADORI, ENZO", "localidad": "ROSARIO", "calle": "SAN MARTIN", "altura": "1234",
           "torre_piso_depto": "", "entre_calles": "", "tipo_domicilio": "Casa", "nombre": "PEREZ JUAN",
           "documento": "30123456", "fecha_nacimiento": "1990-05-20", "telefono": "3415550000", "telefono_alt": "",
           "email": "", "cantidad_tv": "N/A", "plan_id_label": "500MB - FIBRA 500 MB", "ot": "OT1", "sds": "SDS2",
           "fecha_pactada": "2026-09-30", "franja": "PM"}
    row.update(cambios)
    return row


def respuestas(row, preguntas=PREGUNTAS):
    url, avisos = formulario_baf.link_precargado(LINK, preguntas, row)
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}, avisos, url


class FormularioBaf(unittest.TestCase):
    def test_precarga_los_campos(self):
        r, sin_opcion, url = respuestas(gestion())
        self.assertTrue(url.startswith("https://docs.google.com/forms/d/e/ABC123/viewform?usp=pp_url&"))
        self.assertEqual(sin_opcion, [])
        self.assertEqual(r["entry.2"], "ENZO AMADORI")      # «APELLIDO, NOMBRE» en Nodo
        self.assertEqual(r["entry.3"], "Rosario")
        self.assertEqual(r["entry.7"], "Casa")
        self.assertEqual(r["entry.9"], "DNI")
        self.assertEqual(r["entry.11"], "20/05/1990")
        self.assertEqual(r["entry.14"], "Duo")
        self.assertEqual(r["entry.15"], "500 MB")
        self.assertEqual(r["entry.17"], "OT1 SDS2 30/09/2026 PM")
        self.assertEqual(r["entry.1"], "Local")
        self.assertEqual(r["entry.21"], "Solicitud de preventa")
        self.assertEqual(r["entry.19"], "emarceiba3rosario@gmail.com")   # el del local, no el del cliente
        self.assertNotIn("entry.16", r)   # sin TV, sin decos

    def test_con_tv_y_cuit(self):
        r, _, _ = respuestas(gestion(cantidad_tv="2", documento="20301234567"))
        self.assertEqual((r["entry.9"], r["entry.14"], r["entry.15"], r["entry.16"]),
                         ("CUIT", "Triple CUIT", "500 MB + TV", "2"))

    def test_plan_con_tv_en_el_codigo(self):
        r, _, _ = respuestas(gestion(plan_id_label="800MB + TV HD - FIBRA 800 MB + TV"))
        self.assertEqual((r["entry.14"], r["entry.15"]), ("Triple", "800 MB + TV"))
        self.assertNotIn("entry.16", r)   # los decos solo si está cargada la cantidad de TV

    def test_observaciones_sin_lo_que_falta(self):
        r, _, _ = respuestas(gestion(ot="", sds="", fecha_pactada="", franja=""))
        self.assertNotIn("entry.17", r)
        r, _, _ = respuestas(gestion(sds="", franja=""))
        self.assertEqual(r["entry.17"], "OT1 30/09/2026")

    def test_valor_que_no_es_opcion_queda_vacio(self):
        r, sin_opcion, _ = respuestas(gestion(localidad="FUNES", vendedor_id_label="GOMEZ, ANA"))
        self.assertNotIn("entry.3", r)
        self.assertNotIn("entry.2", r)
        self.assertEqual(len(sin_opcion), 1)
        self.assertIn("Vendedor (GOMEZ, ANA)\n    Localidad (FUNES)", sin_opcion[0])

    def test_formulario_con_una_pregunta_nueva_y_otra_renombrada(self):
        """Una pregunta que Nodo no conoce queda vacía; una que Nodo precarga y ya no está se avisa."""
        preguntas = dict(PREGUNTAS, **{"COMO NOS CONOCIO": (20, ["Redes", "Amigos"])})
        preguntas["CELULAR"] = preguntas.pop("TELEFONO")
        r, avisos, _ = respuestas(gestion(), preguntas)
        self.assertNotIn("entry.20", r)
        self.assertEqual(r["entry.3"], "Rosario")   # el resto sigue igual
        self.assertEqual(len(avisos), 1)
        self.assertIn("No están en el formulario", avisos[0])
        self.assertIn("Telefono", avisos[0])

    def test_link_invalido(self):
        with self.assertRaises(formulario_baf.FormularioError):
            formulario_baf.link_precargado("https://example.com/form", PREGUNTAS, gestion())


if __name__ == "__main__":
    unittest.main()
