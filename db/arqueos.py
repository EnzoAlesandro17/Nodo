"""Arqueo de caja (traído de MyTools): caja fuerte (CF) + caja chica (CC) - saldo del sistema (SS).

`resultado` = CF + CC - SS: positivo sobra, negativo falta. Se arrastra: la variación de cada arqueo es su resultado
menos el del arqueo anterior (el primero, su resultado), y al cargar uno nuevo la caja fuerte se precarga con la del
anterior. Como en MyTools, los arqueos no se editan ni se borran (para evitar cambios de mala fe): solo se cargan,
se consultan y se exportan.

Cada monto se puede escribir como una suma, en formato es-AR: "700.000", "+100.000+50.000+2.000", "307.221,43".
"""
import re
from datetime import datetime

from db import connection

EPS = 0.005
_NUMERO = re.compile(r"[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?|[+-]?\d+(?:,\d+)?")


def evaluar(texto):
    """Suma de todos los números escritos (con su signo). Lo que no es un número se ignora; vacío = 0."""
    limpio = re.sub(r"\s+", "", str(texto or ""))
    return round(sum((float(t.replace(".", "").replace(",", ".")) for t in _NUMERO.findall(limpio)), 0.0), 2)


def etiqueta(monto):
    """'Sobra $ …', 'Falta $ …' o 'Bien'."""
    from ui.formatting import fmt_money   # acá para no depender de la interfaz al importar el módulo
    if monto > EPS:
        return f"Sobra {fmt_money(monto)}"
    if monto < -EPS:
        return f"Falta {fmt_money(-monto)}"
    return "Bien"


def listar():
    """Todos los arqueos activos, el más reciente primero, con `empleados` (lista de nombres) y `variacion`."""
    db = connection.get()
    nombres = {}
    for r in db.execute("SELECT arqueo_id, nombre FROM arqueo_empleados ORDER BY rowid"):
        nombres.setdefault(r["arqueo_id"], []).append(r["nombre"])
    rows = [dict(r) for r in db.execute("SELECT * FROM arqueos WHERE activo = 1 ORDER BY fecha, id")]
    previo = None
    for r in rows:
        r["empleados"] = nombres.get(r["id"], [])
        r["variacion"] = round(r["resultado"] - (previo["resultado"] if previo else 0.0), 2)
        previo = r
    rows.reverse()
    return rows


def anterior(fecha=None):
    """El último arqueo anterior a `fecha` (por defecto, el último de todos), o None."""
    fecha = fecha or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return next((r for r in listar() if r["fecha"] <= fecha), None)


def registrar(empleados, cf, cc, sc, fecha=None):
    """Guarda un arqueo nuevo con `cf`, `cc` y `sc` tal como se escribieron. ValueError si no hay empleados."""
    empleados = [e.strip() for e in empleados if e and e.strip()]
    if not empleados:
        raise ValueError("Elegí al menos un empleado.")
    cf, cc, sc = (str(x).strip() or "0" for x in (cf, cc, sc))
    cf_val, cc_val, sc_val = evaluar(cf), evaluar(cc), evaluar(sc)
    fecha = fecha or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = connection.get()
    with db:
        arqueo_id = db.execute(
            "INSERT INTO arqueos (fecha, cf_expr, cf_val, cc_expr, cc_val, sc_expr, sc_val, resultado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fecha, cf, cf_val, cc, cc_val, sc, sc_val, round(cf_val + cc_val - sc_val, 2))).lastrowid
        db.executemany("INSERT INTO arqueo_empleados (arqueo_id, nombre) VALUES (?, ?)",
                       [(arqueo_id, e) for e in empleados])
    return arqueo_id


def exportar_xlsx(path):
    """Todos los arqueos, del más viejo al más nuevo, en un Excel (mismas columnas que MyTools). Devuelve la cantidad."""
    from openpyxl import Workbook   # solo hace falta al exportar

    wb = Workbook()
    ws = wb.active
    ws.title = "Arqueos"
    ws.append(["Fecha y hora", "Empleados", "Caja fuerte", "Caja chica", "Saldo sistema", "Resultado"])
    rows = list(reversed(listar()))
    for r in rows:
        ws.append([datetime.strptime(r["fecha"], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M"),
                   ", ".join(r["empleados"]), r["cf_val"], r["cc_val"], r["sc_val"], r["resultado"]])
    for col in ws.columns:
        ws.column_dimensions[col[0].column_letter].width = 18
    wb.save(path)
    return len(rows)
