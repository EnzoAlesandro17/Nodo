"""Repositorio genérico para tablas de stock con borrado lógico (columna `activo`)."""
from db import connection


def _like_escape(text):
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


AMBIGUO = "ambiguo"   # valor de all_by_key cuando dos registros activos comparten clave


class Repo:
    clave = "codigo"   # campo con el que las importaciones identifican cada registro (empleados: el nombre)

    def __init__(self, table, fields, filter_key, order="codigo"):
        self.table = table
        self.order = order   # ORDER BY del listado
        self.fields = fields
        self.keys = [f.key for f in fields if f.kind not in ("multi", "pagos", "calc")]   # columnas de la tabla
        self.text_keys = [f.key for f in fields if f.kind in ("text", "choice", "list", "email")]
        assert filter_key in self.keys
        self.filter_key = filter_key

    @property
    def name_key(self):
        """Campo que acompaña a la clave para reconocer un registro."""
        return "descripcion" if "descripcion" in self.keys else "nombre"

    @property
    def _db(self):
        return connection.get()

    # --- lectura -------------------------------------------------------
    def list(self, search="", filter_value=None):
        """Productos activos. Cada palabra de `search` debe aparecer en algún campo de texto."""
        where, params = ["activo = 1"], []
        for token in search.upper().split():
            like = f"%{_like_escape(token)}%"
            where.append("(" + " OR ".join(f"{k} LIKE ? ESCAPE '\\'" for k in self.text_keys) + ")")
            params += [like] * len(self.text_keys)
        if filter_value:
            where.append(f"{self.filter_key} = ?")
            params.append(filter_value)
        sql = f"SELECT * FROM {self.table} WHERE {' AND '.join(where)} ORDER BY {self.order}"
        return [dict(r) for r in self._db.execute(sql, params)]

    def distinct(self, key):
        """Valores ya cargados de un campo (entre los activos), para filtros y sugerencias."""
        assert key in self.keys
        sql = f"SELECT DISTINCT {key} FROM {self.table} WHERE activo = 1 AND {key} <> '' ORDER BY {key}"
        return [r[0] for r in self._db.execute(sql)]

    def get_by_codigo(self, codigo):
        """Busca por código entre activos Y dados de baja."""
        row = self._db.execute(f"SELECT * FROM {self.table} WHERE codigo = ?", (codigo,)).fetchone()
        return dict(row) if row else None

    def all_by_key(self):
        """Todos los registros (activos y dados de baja) indexados por su clave. Si dos activos comparten
        clave, el valor es AMBIGUO; un activo prevalece sobre un dado de baja con la misma clave."""
        out = {}
        for r in self._db.execute(f"SELECT * FROM {self.table} ORDER BY activo, id"):
            row, key = dict(r), r[self.clave]
            if out.get(key) == AMBIGUO:
                continue
            prev = out.get(key)
            out[key] = AMBIGUO if prev and prev["activo"] and row["activo"] else row
        return out

    # --- escritura -----------------------------------------------------
    # Las variantes _xxx_row no confirman la transacción: las subclases las combinan con otros cambios.
    def _insert_row(self, data):
        cols = ", ".join(self.keys)
        marks = ", ".join("?" for _ in self.keys)
        cur = self._db.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({marks})",
                               [data[k] for k in self.keys])
        return cur.lastrowid

    def _update_row(self, row_id, data):
        sets = ", ".join(f"{k} = ?" for k in self.keys)
        self._db.execute(f"UPDATE {self.table} SET {sets} WHERE id = ?",
                         [data[k] for k in self.keys] + [row_id])

    def _deactivate_row(self, row_id):
        self._db.execute(f"UPDATE {self.table} SET activo = 0 WHERE id = ?", (row_id,))

    def insert(self, data):
        with self._db:
            return self._insert_row(data)

    def update(self, row_id, data):
        with self._db:
            self._update_row(row_id, data)

    def update_fields(self, row_id, changes):
        """Cambia solo algunos campos `{campo: valor}` de un registro."""
        assert set(changes) <= set(self.keys)
        sets = ", ".join(f"{k} = ?" for k in changes)
        with self._db:
            self._db.execute(f"UPDATE {self.table} SET {sets} WHERE id = ?", list(changes.values()) + [row_id])

    def deactivate(self, row_id):
        with self._db:
            self._deactivate_row(row_id)

    def reactivate(self, row_id, data):
        """Vuelve a dar de alta un producto dado de baja, con los datos indicados."""
        self.update(row_id, data)
        with self._db:
            self._db.execute(f"UPDATE {self.table} SET activo = 1 WHERE id = ?", (row_id,))

    def apply_import(self, inserts, updates, bajas=()):
        """Altas completas, cambios parciales `(id, {campo: valor})` y bajas (ids), todo en una transacción."""
        cols = ", ".join(self.keys)
        marks = ", ".join("?" for _ in self.keys)
        with self._db:
            for data in inserts:
                self._db.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({marks})",
                                 [data[k] for k in self.keys])
            for row_id, changes in updates:
                assert set(changes) <= set(self.keys) - {"stock"}
                sets = ", ".join(f"{k} = ?" for k in changes)
                self._db.execute(f"UPDATE {self.table} SET {sets} WHERE id = ?",
                                 list(changes.values()) + [row_id])
            for row_id in bajas:
                self._deactivate_row(row_id)
