"""Importación y exportación masiva de tablas vía CSV (sección Data).

Reglas (ver HOJA_DE_RUTA.txt):
- El stock nunca se lee ni se modifica: la columna Stock del archivo se ignora.
- Cada fila se busca por la clave de la tabla (`repo.clave`: el código; en empleados, el nombre).
- Clave existente -> se modifica, pero solo si la descripción es similar a la actual (en las
  tablas que tienen descripción); si no, queda como conflicto y no se aplica salvo que se pida.
- Clave inexistente -> alta con stock 0. Registros dados de baja se omiten.
- Celda vacía = "dejar como está". Las columnas que no vienen en el archivo no se tocan.
- Lo que no aparece en el archivo no se toca, salvo que se pida darlo de baja (el archivo
  reemplaza a la lista).
"""
import csv
import difflib
import io
import re
import unicodedata
from datetime import datetime

from db import refs
from db.repo import AMBIGUO
from ui.formatting import fmt_date, fmt_money, money_to_input, parse_date, parse_int, parse_money

SIMILARITY_MIN = 0.7   # proporción mínima de parecido entre descripciones (0 a 1)
DELIMITER = ";"        # el de Excel en es-AR (la coma es el separador decimal)


class CsvError(Exception):
    """Error que impide leer el archivo (se muestra al usuario tal cual)."""


class CeldaError(ValueError):
    """Una celda con un valor que no sirve; el mensaje se muestra tal cual."""


def importable_fields(repo):
    """Campos que el archivo puede traer: todos menos el stock, las casillas y las columnas calculadas."""
    return [f for f in repo.fields if f.key != "stock" and f.kind not in ("bool", "calc")]


def _ascii(text):
    return unicodedata.normalize("NFD", text).encode("ascii", "ignore").decode()


def _norm_header(text):
    return re.sub(r"[^a-z0-9]+", "_", _ascii(text).lower()).strip("_")


def _norm_desc(text):
    return re.sub(r"[^A-Z0-9]", "", _ascii(text).upper())


def similar(a, b):
    """Descripciones parecidas: mismos números (modelos, versiones) y texto casi igual."""
    na, nb = _norm_desc(a), _norm_desc(b)
    if na == nb:
        return True
    if sorted(re.findall(r"\d+", a)) != sorted(re.findall(r"\d+", b)):
        return False
    return difflib.SequenceMatcher(None, na, nb).ratio() >= SIMILARITY_MIN


# --- lectura -----------------------------------------------------------
def _read_rows(path):
    with open(path, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    lines = text.splitlines()
    if not lines:
        raise CsvError("El archivo está vacío.")
    delim = max(";,\t", key=lines[0].count)
    return list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))   # respeta los saltos de línea entre comillas


class Plan:
    def __init__(self, repo):
        self.updates = []      # {id, clave, nombre, changes: {campo: (viejo, nuevo)} (textos), values: {key: nuevo}}
        self.conflicts = []    # ídem
        self.inserts = []      # {clave, nombre, resumen, data}
        self.skipped = []      # (fila, clave, motivo)
        self.missing = []      # {id, clave, nombre}: activos que no están en el archivo
        self.unchanged = 0
        self.columns = []      # campos reconocidos del archivo
        self.ignored = []      # encabezados que no se usaron
        by_key = {f.key: f for f in repo.fields}
        self.clave_label = by_key[repo.clave].label
        self.nombre_label = by_key[repo.name_key].label
        self.tiene_stock = "stock" in by_key
        self.tiene_descripcion = "descripcion" in by_key


def _parse_cell(field, cell, sucursales):
    if field.kind == "money":
        return parse_money(cell)
    if field.kind == "int":
        return parse_int(cell, field.signed)
    if field.kind == "multi":   # sucursales de un empleado, por nombre clave
        codes = [c for c in re.split(r"\s*[,/|]\s*", cell.upper()) if c]
        unknown = [c for c in codes if c not in sucursales]
        if unknown:
            raise CeldaError("no existe la sucursal " + ", ".join(unknown) + ".")
        return sorted({sucursales[c] for c in codes})
    if field.kind == "date":   # dd/mm/aaaa (también acepta aaaa-mm-dd, que es como lo guarda la base)
        try:
            return parse_date(cell)
        except ValueError:
            try:
                return datetime.strptime(cell, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                raise CeldaError(f"«{cell}» no es una fecha (usá dd/mm/aaaa).") from None
    if field.kind == "email":
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", cell):
            raise CeldaError(f"«{cell}» no parece una dirección de mail.")
        return cell.lower()
    return cell.upper()


def _show(field, value, sucursales_by_id):
    if field.kind == "money":
        return fmt_money(value)
    if field.kind == "date":
        return fmt_date(value) or "(vacío)"
    if field.kind == "multi":
        return ", ".join(sucursales_by_id[i] for i in value if i in sucursales_by_id) or "(ninguna)"
    return str(value) if value != "" else "(vacío)"


def build_plan(repo, path):
    """Compara el archivo con la base y devuelve un Plan. No escribe nada."""
    rows = _read_rows(path)
    by_header = {}
    for f in importable_fields(repo):
        by_header[_norm_header(f.key)] = f
        by_header[_norm_header(f.label)] = f

    plan = Plan(repo)
    col_field = {}
    for i, h in enumerate(rows[0]):
        f = by_header.get(_norm_header(h))
        if f and f not in col_field.values():
            col_field[i] = f
        elif h.strip():
            plan.ignored.append(h.strip())
    plan.columns = list(col_field.values())
    if not any(f.key == repo.clave for f in plan.columns):
        raise CsvError(f"El archivo necesita una columna «{plan.clave_label}» en la primera fila.")

    sucursales = {}
    if any(f.kind == "multi" for f in plan.columns):
        sucursales = {codigo: i for i, codigo in refs.codigos("sucursales")}
    sucursales_by_id = {i: c for c, i in sucursales.items()}
    fields = {f.key: f for f in repo.fields}

    existing = repo.all_by_key()
    seen = set()
    for line, cells in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in cells):
            continue
        values, error = {}, None
        for i, f in col_field.items():
            cell = cells[i].strip() if i < len(cells) else ""
            if not cell:
                continue
            try:
                values[f.key] = _parse_cell(f, cell, sucursales)
            except CeldaError as e:
                error = f"{f.label}: {e}"
                break
            except ValueError:
                error = f"{f.label}: «{cell}» no es un número válido."
                break
        clave = values.get(repo.clave, "")
        if error or not clave:
            plan.skipped.append((line, clave, error or f"Fila sin {plan.clave_label.lower()}."))
            continue
        if clave in seen:
            plan.skipped.append((line, clave, "Repetido en el archivo (se usó la primera fila)."))
            continue
        seen.add(clave)

        cur = existing.get(clave)
        if cur is None:
            missing = [f.label for f in repo.fields if f.required and f.key not in values]
            if missing:
                plan.skipped.append((line, clave, "Es nuevo, pero falta " + ", ".join(missing) + "."))
                continue
            data = {f.key: [] if f.kind == "multi" else 0 if f.kind in ("int", "bool")
                    else 0.0 if f.kind == "money" else "" for f in repo.fields}
            data.update(values)
            resumen = " · ".join(f"{fields[k].label}: {_show(fields[k], v, sucursales_by_id)}"
                                 for k, v in data.items() if k not in (repo.clave, repo.name_key)
                                 and v not in ("", 0, 0.0, []) and fields[k].kind != "bool")
            plan.inserts.append({"clave": clave, "nombre": data.get(repo.name_key, ""),
                                 "resumen": resumen, "data": data})
            continue
        if cur == AMBIGUO:
            plan.skipped.append((line, clave, "Hay más de un registro activo con ese nombre: no se sabe cuál modificar."))
            continue
        if not cur["activo"]:
            plan.skipped.append((line, clave, "Dado de baja: se omite."))
            continue

        changes = {}
        for k, new in values.items():
            old = cur[k]
            if k == repo.clave:
                continue
            if isinstance(new, float):
                different = abs(old - new) >= 0.005
            elif isinstance(new, list):
                different = sorted(old) != new
            else:
                different = old != new
            if different:
                changes[k] = (old, new)
        if not changes:
            plan.unchanged += 1
            continue
        entry = {"id": cur["id"], "clave": clave, "nombre": cur[repo.name_key],
                 "changes": {fields[k].label: (_show(fields[k], old, sucursales_by_id),
                                               _show(fields[k], new, sucursales_by_id))
                             for k, (old, new) in changes.items()},
                 "values": {k: new for k, (_, new) in changes.items()}}
        if "descripcion" in changes and not similar(cur["descripcion"], values["descripcion"]):
            plan.conflicts.append(entry)
        else:
            plan.updates.append(entry)

    plan.missing = [{"id": cur["id"], "clave": clave, "nombre": cur[repo.name_key]}
                    for clave, cur in existing.items()
                    if cur != AMBIGUO and cur["activo"] and clave not in seen]
    return plan


def apply_plan(repo, plan, include_conflicts=False, deactivate_missing=False):
    """Escribe el plan en una sola transacción. Devuelve (modificados, altas, bajas)."""
    updates = plan.updates + (plan.conflicts if include_conflicts else [])
    bajas = [m["id"] for m in plan.missing] if deactivate_missing else []
    repo.apply_import([p["data"] for p in plan.inserts], [(u["id"], u["values"]) for u in updates], bajas)
    return len(updates), len(plan.inserts), len(bajas)


# --- exportación -------------------------------------------------------
def export_csv(repo, path):
    """Escribe los registros activos (sin stock) en un CSV que se puede editar y volver a importar."""
    fields = importable_fields(repo)
    rows = repo.list()
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=DELIMITER)
        w.writerow([f.label for f in fields])
        for r in rows:
            w.writerow([money_to_input(r[f.key]) if f.kind == "money"
                        else fmt_date(r[f.key]) if f.kind == "date"
                        else r[f.key + "_label"] if f.kind == "multi" else r[f.key] for f in fields])
    return len(rows)
