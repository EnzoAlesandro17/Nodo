"""Precarga del formulario de Google de las BAF: arma el link del formulario con los datos de una gestión ya
puestos, para revisarlo en el navegador y enviarlo a mano.

El link se guarda en ajustes (cambia cada mes). Las preguntas se leen del propio formulario al abrirlo y se
reconocen por su título (no por su número interno), así que un formulario nuevo con las mismas preguntas
sigue andando. En las preguntas de opciones solo se precarga un valor que coincida con una opción; si no, queda
vacía para completarla a mano. Una pregunta nueva que Nodo no conoce queda vacía; una que Nodo precarga y ya no
está en el formulario (p. ej. porque le cambiaron el título) se avisa. Acometimientos y las de portabilidad quedan
vacías. "Enviarme una copia de mis respuestas" no se puede tildar desde el link: se tilda a mano.
"""
import json
import re
import unicodedata
import urllib.request
from urllib.parse import urlencode

from db import ajustes
from ui.formatting import fmt_date

CLAVE = "formulario_baf"   # clave del link en ajustes
MODO = "Local"                              # las BAF se cargan desde el local
MAIL = "emarceiba3rosario@gmail.com"        # en el formulario va siempre el mail del local, no el del cliente
ESTADO = "Solicitud de preventa"            # el estado con que se carga toda venta de BAF


class FormularioError(Exception):
    """No se pudo leer el formulario (se muestra al usuario tal cual)."""


def link_guardado():
    return ajustes.leer(CLAVE, "")


def guardar_link(link):
    ajustes.guardar(CLAVE, link.strip())


def _norm(text):
    """'TELÉFONO ' -> 'TELEFONO'; 'PISO Y DEPTO-\\nNUMERO...' -> 'PISO Y DEPTO NUMERO...'."""
    text = "".join(c for c in unicodedata.normalize("NFD", str(text).upper()) if not unicodedata.combining(c))
    return re.sub(r"[^A-Z0-9]+", " ", text).strip()


def _base(link):
    """El link del formulario sin '/viewform?...' (el que se copia de la barra o de 'Enviar')."""
    m = re.match(r"(https://docs\.google\.com/forms/d/e/[\w-]+)", link.strip())
    if not m:
        raise FormularioError("El link no parece de un formulario de Google (docs.google.com/forms/d/e/...).")
    return m.group(1)


# --- lectura del formulario ------------------------------------------------
def preguntas(link):
    """{título normalizado: (id de la respuesta, [opciones])}, leído del formulario publicado."""
    try:
        with urllib.request.urlopen(_base(link) + "/viewform", timeout=15) as resp:
            html = resp.read().decode("utf-8")
    except OSError as e:
        raise FormularioError(f"No se pudo abrir el formulario (¿hay internet?).\n\n{e}") from None
    m = re.search(r"FB_PUBLIC_LOAD_DATA_ = (.*?);\s*</script>", html, re.S)
    if not m:
        raise FormularioError("No se pudieron leer las preguntas del formulario (¿pide iniciar sesión?).")
    out = {}
    for item in json.loads(m.group(1))[1][1]:
        for entry in item[4] or []:   # las secciones y los textos sueltos no tienen respuesta
            out[_norm(item[1])] = (entry[0], [o[0] for o in entry[1] or []])
    return out


# --- respuestas de una gestión -----------------------------------------------
def _codigo_plan(row):
    return (row.get("plan_id_label") or "").split(" - ")[0]   # «500MB + TV HD - FIBRA 500 MB + TV» -> el código


def _hay_tv(row):
    return row["cantidad_tv"] in ("1", "2", "3") or "TV" in _codigo_plan(row).upper()


def _es_cuit(row):
    return len(row["documento"]) == 11


def _plan(row):
    """'500MB' -> '500 MB'; '500MB + TV HD' (o con TV cargada) -> '500 MB + TV', como las opciones del formulario."""
    m = re.match(r"\s*(\d+)\s*MB", _codigo_plan(row), re.I)
    return m and f"{m.group(1)} MB" + (" + TV" if _hay_tv(row) else "")


def _mismas_palabras(a, b):
    """'AMADORI, ENZO' (Nodo) y 'ENZO AMADORI' (formulario) son la misma persona."""
    return sorted(_norm(a).split()) == sorted(_norm(b).split())


def respuestas(row):
    """{título normalizado de la pregunta: valor} con lo que Nodo sabe de la gestión `row` (de repos.baf.list)."""
    observaciones = " ".join(v for v in (row["ot"], row["sds"], fmt_date(row["fecha_pactada"]), row["franja"]) if v)
    return {
        "MODO": MODO,
        "VENDEDOR": row.get("vendedor_id_label") or "",
        "LOCALIDAD": row["localidad"],
        "CALLE": row["calle"],
        "ALTURA": row["altura"],
        "PISO Y DEPTO": row["torre_piso_depto"],
        "ENTRE CALLES": row["entre_calles"],
        "INMUEBLE": row["tipo_domicilio"],
        "NOMBRE Y APELLIDO": row["nombre"],
        "TIPO DOC": ("CUIT" if _es_cuit(row) else "DNI") if row["documento"] else "",
        "NRO DOCUMENTO": row["documento"],
        "FECHA NAC": fmt_date(row["fecha_nacimiento"]),
        "TELEFONO": row["telefono"],
        "TELEFONO ALTERNATIVO": row["telefono_alt"],
        "MAIL": MAIL,
        "SERVICIO": ("Triple" if _hay_tv(row) else "Duo") + (" CUIT" if _es_cuit(row) else ""),
        "PLAN": _plan(row),
        "DECOS": row["cantidad_tv"] if _hay_tv(row) else "",
        "ESTADO": ESTADO,
        "OBSERVACIONES": observaciones,
    }


_POR_COMIENZO = ("PISO Y DEPTO",)   # títulos largos que se reconocen por cómo empiezan


def _pregunta(preguntas_, titulo):
    """La pregunta con ese título, o, en las de _POR_COMIENZO, la que empieza con él ('PISO Y DEPTO - NUMERO DE
    TIRA...'). Las demás tienen que coincidir enteras: si no, sin 'TELEFONO' se tomaría 'TELEFONO ALTERNATIVO'."""
    if titulo in preguntas_:
        return preguntas_[titulo]
    if titulo in _POR_COMIENZO:
        return next((p for t, p in preguntas_.items() if t.startswith(titulo + " ")), None)
    return None


def _opcion(opciones, valor):
    """La opción del formulario que corresponde a `valor`, o None."""
    compacto = _norm(valor).replace(" ", "")
    return (next((o for o in opciones if _norm(o).replace(" ", "") == compacto), None)
            or next((o for o in opciones if _mismas_palabras(o, valor)), None))


def link_precargado(link, preguntas_, row):
    """Link del formulario con las respuestas de `row` ya puestas. Devuelve (link, avisos): las preguntas que no se
    pudieron precargar porque el valor no coincide con ninguna opción o porque no están en el formulario."""
    params, sin_opcion, no_estan = [("usp", "pp_url")], [], []
    for titulo, valor in respuestas(row).items():
        pregunta = _pregunta(preguntas_, titulo)
        if pregunta is None:
            no_estan.append(titulo.capitalize())
            continue
        if not valor:
            continue
        entry_id, opciones = pregunta
        if opciones:
            valor_opcion = _opcion(opciones, valor)
            if valor_opcion is None:
                sin_opcion.append(f"{titulo.capitalize()} ({valor})")
                continue
            valor = valor_opcion
        params.append((f"entry.{entry_id}", valor))
    avisos = []
    if sin_opcion:
        avisos.append("No coinciden con ninguna opción del formulario (elegilas a mano):\n    " + "\n    ".join(sin_opcion))
    if no_estan:
        avisos.append("No están en el formulario (¿les cambiaron el nombre?), completalas a mano si siguen:\n    "
                      + "\n    ".join(no_estan))
    return f"{_base(link)}/viewform?{urlencode(params)}", avisos
