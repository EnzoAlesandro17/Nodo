"""Repositorios de Administración: áreas, sucursales, empleados y cuentas."""
from db import refs
from db.repo import AMBIGUO, Repo, _like_escape
from models import AREAS, CUENTAS, DESCUENTOS, EMPLEADOS, PLANES, SUCURSALES


class SucursalRepo(Repo):
    """Sucursales con su área: cada fila trae `area_id_label` («ROS - ROSARIO»), que también sirve de filtro."""

    _AREA = refs.label_sql("areas", "a")

    def list(self, search="", filter_value=None):
        searchable = [f"s.{k}" for k in self.text_keys] + refs.search_columns("areas", "a")
        where, params = ["s.activo = 1"], []
        for token in search.upper().split():
            where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in searchable) + ")")
            params += [f"%{_like_escape(token)}%"] * len(searchable)
        if filter_value:
            where.append(f"{self._AREA} = ?")
            params.append(filter_value)
        sql = (f"SELECT s.*, COALESCE({self._AREA}, '') AS area_id_label FROM sucursales s "
               f"LEFT JOIN areas a ON a.id = s.area_id WHERE {' AND '.join(where)} ORDER BY s.{self.order}")
        return [dict(r) for r in self._db.execute(sql, params)]

    def distinct(self, key):
        if key != "area_id":
            return super().distinct(key)
        sql = (f"SELECT DISTINCT {self._AREA} AS label FROM sucursales s JOIN areas a ON a.id = s.area_id "
               "WHERE s.activo = 1 ORDER BY label")
        return [r[0] for r in self._db.execute(sql)]

    def contar_por_area(self, area_id):
        """Sucursales activas del área (para avisar antes de darla de baja)."""
        return self._db.execute("SELECT COUNT(*) FROM sucursales WHERE activo = 1 AND area_id = ?",
                                (area_id,)).fetchone()[0]


class EmpleadoRepo(Repo):
    """Empleados con sus sucursales (relación muchos a muchos en `empleado_sucursal`).

    Cada fila trae `sucursales` (lista de ids, para el formulario) y `sucursales_label`
    (códigos separados por coma, para la tabla). Solo cuentan las sucursales activas.
    """

    _CODES = ("(SELECT group_concat(codigo, ', ') FROM (SELECT s.codigo FROM empleado_sucursal es "
              "JOIN sucursales s ON s.id = es.sucursal_id WHERE es.empleado_id = e.id AND s.activo = 1 "
              "ORDER BY s.codigo))")

    def list(self, search="", filter_value=None):
        searchable = [f"e.{k}" for k in self.text_keys] + [self._CODES]
        where, params = ["e.activo = 1"], []
        for token in search.upper().split():
            where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in searchable) + ")")
            params += [f"%{_like_escape(token)}%"] * len(searchable)
        if filter_value:
            where.append(f"e.{self.filter_key} = ?")
            params.append(filter_value)
        sql = (f"SELECT e.*, {self._CODES} AS sucursales_label FROM empleados e "
               f"WHERE {' AND '.join(where)} ORDER BY e.nombre")
        rows = [dict(r) for r in self._db.execute(sql, params)]
        links = {}
        for r in self._db.execute("SELECT es.empleado_id, es.sucursal_id FROM empleado_sucursal es "
                                  "JOIN sucursales s ON s.id = es.sucursal_id WHERE s.activo = 1"):
            links.setdefault(r[0], []).append(r[1])
        for row in rows:
            row["sucursales"] = links.get(row["id"], [])
        return rows

    def _set_sucursales_row(self, row_id, sucursal_ids):   # sin confirmar la transacción
        self._db.execute("DELETE FROM empleado_sucursal WHERE empleado_id = ? AND sucursal_id IN "
                         "(SELECT id FROM sucursales WHERE activo = 1)", (row_id,))
        self._db.executemany("INSERT OR IGNORE INTO empleado_sucursal (empleado_id, sucursal_id) VALUES (?, ?)",
                             [(row_id, s) for s in sucursal_ids])

    def _set_sucursales(self, row_id, sucursal_ids):
        """Reemplaza las sucursales activas del empleado (las de sucursales dadas de baja se conservan)."""
        with self._db:
            self._set_sucursales_row(row_id, sucursal_ids)

    # --- importación masiva: los empleados se identifican por el nombre ---
    clave = "nombre"

    def all_by_key(self):
        rows = super().all_by_key()
        links = {}
        for r in self._db.execute("SELECT es.empleado_id, es.sucursal_id FROM empleado_sucursal es "
                                  "JOIN sucursales s ON s.id = es.sucursal_id WHERE s.activo = 1"):
            links.setdefault(r[0], []).append(r[1])
        for row in rows.values():
            if row != AMBIGUO:
                row["sucursales"] = sorted(links.get(row["id"], []))
        return rows

    def apply_import(self, inserts, updates, bajas=()):
        with self._db:
            for data in inserts:
                row_id = self._insert_row(data)
                self._set_sucursales_row(row_id, data["sucursales"])
            for row_id, changes in updates:
                cols = {k: v for k, v in changes.items() if k != "sucursales"}
                if cols:
                    sets = ", ".join(f"{k} = ?" for k in cols)
                    self._db.execute(f"UPDATE empleados SET {sets} WHERE id = ?", list(cols.values()) + [row_id])
                if "sucursales" in changes:
                    self._set_sucursales_row(row_id, changes["sucursales"])
            for row_id in bajas:
                self._deactivate_row(row_id)

    def insert(self, data):
        row_id = super().insert(data)
        self._set_sucursales(row_id, data["sucursales"])
        return row_id

    def update(self, row_id, data):
        super().update(row_id, data)
        self._set_sucursales(row_id, data["sucursales"])


areas = Repo("areas", AREAS, filter_key="codigo")
sucursales = SucursalRepo("sucursales", SUCURSALES, filter_key="area_id")
cuentas = Repo("cuentas", CUENTAS, filter_key="tipo")
empleados = EmpleadoRepo("empleados", EMPLEADOS, filter_key="rol")
planes = Repo("planes", PLANES, filter_key="categoria",   # el filtro por categoría separa los de líneas de los de BAF
              order="categoria, CAST(codigo AS INTEGER), codigo")   # 2GB antes que 10GB
descuentos = Repo("descuentos", DESCUENTOS, filter_key="codigo")
