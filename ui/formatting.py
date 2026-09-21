"""Formato y lectura de números en estilo es-AR (1.234,56)."""
import re
from datetime import datetime


def fmt_money(value):
    s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {s}"


def fmt_int(value):
    return f"{value:,}".replace(",", ".")


def money_to_input(value):
    """Valor para precargar en un campo de edición (sin separador de miles)."""
    return f"{value:.2f}".replace(".", ",")


def parse_money(text):
    """'1.234,56' | '1234,56' | '1234.56' | '1.500' | '' (=0) -> float. ValueError si es inválido."""
    text = text.replace("$", "").replace(" ", "")
    if not text:
        return 0.0
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", text):  # '1.500' = mil quinientos
        text = text.replace(".", "")
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        raise ValueError(text)
    return round(float(text), 2)


def parse_int(text, signed=False):
    text = text.replace(".", "").replace(" ", "")
    if not text:
        return 0
    if not text.lstrip("-" if signed else "").isdigit() or text.count("-") > 1 or text.endswith("-"):
        raise ValueError(text)
    return int(text)


# --- fecha y hora: se guarda "AAAA-MM-DD HH:MM:SS" (ordena bien como texto) ---
def now_iso():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def fmt_datetime(iso):
    """'2026-09-19 15:11:42' -> '19/09/2026 15:11'. Si no tiene hora (registros viejos), solo la fecha."""
    day, _, time = iso.partition(" ")
    y, m, d = day.split("-")
    return f"{d}/{m}/{y} {time[:5]}".strip()


def fmt_date(iso):
    """'2026-09-19' -> '19/09/2026' (vacío queda vacío)."""
    if not iso:
        return ""
    y, m, d = iso[:10].split("-")
    return f"{d}/{m}/{y}"


def parse_date(text):
    """'19/09/2026' -> 'AAAA-MM-DD'. ValueError si es inválida."""
    return datetime.strptime(" ".join(text.split()), "%d/%m/%Y").strftime("%Y-%m-%d")


def parse_datetime(text):
    """'19/09/2026 15:11' | '19/09/2026' (=00:00) -> 'AAAA-MM-DD HH:MM:SS'. ValueError si es inválida."""
    text = " ".join(text.split())
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError(text)
