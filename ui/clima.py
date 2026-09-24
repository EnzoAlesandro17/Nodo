"""Clima de Rosario para el Inicio, de Open-Meteo (gratis, sin clave; el mismo que usaba MyTools).

Se pide en segundo plano: sin internet, o si tarda, el Inicio se ve igual y el clima queda vacío.
"""
import json
import threading
import urllib.request

LATITUD, LONGITUD = -32.95, -60.64   # Rosario
URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code"
       "&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=America%2FArgentina%2FBuenos_Aires")

# códigos WMO que devuelve Open-Meteo
CIELO = {0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado", 3: "Nublado", 45: "Niebla",
         48: "Niebla", 51: "Llovizna", 53: "Llovizna", 55: "Llovizna", 56: "Llovizna helada", 57: "Llovizna helada",
         61: "Lluvia débil", 63: "Lluvia", 65: "Lluvia fuerte", 66: "Lluvia helada", 67: "Lluvia helada",
         71: "Nieve", 73: "Nieve", 75: "Nieve", 77: "Nieve", 80: "Chaparrones", 81: "Chaparrones",
         82: "Chaparrones fuertes", 85: "Nieve", 86: "Nieve", 95: "Tormenta", 96: "Tormenta con granizo",
         99: "Tormenta con granizo"}


def texto(datos):
    """'Rosario 23° · Mayormente despejado · mín 12° máx 24°' a partir de la respuesta de Open-Meteo."""
    actual, dia = datos["current"], datos["daily"]
    return (f"Rosario {round(actual['temperature_2m'])}° · {CIELO.get(actual['weather_code'], '')} · "
            f"mín {round(dia['temperature_2m_min'][0])}° máx {round(dia['temperature_2m_max'][0])}°")


def pedir(widget, al_llegar):
    """Pide el clima en otro hilo y, si llega, llama a `al_llegar(texto)` desde el hilo de la interfaz (tkinter no
    se toca desde otro hilo: la interfaz revisa cada tanto si ya llegó)."""
    resultado = []

    def trabajo():
        try:
            with urllib.request.urlopen(URL.format(lat=LATITUD, lon=LONGITUD), timeout=5) as r:
                resultado.append(texto(json.load(r)))
        except Exception:   # sin internet, servicio caído o respuesta rara: no se muestra nada
            resultado.append(None)

    def revisar(intentos=40):   # hasta 8 segundos
        if not widget.winfo_exists():
            return
        if resultado:
            if resultado[0]:
                al_llegar(resultado[0])
        elif intentos:
            widget.after(200, revisar, intentos - 1)

    threading.Thread(target=trabajo, daemon=True).start()
    widget.after(200, revisar)
