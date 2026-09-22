"""Repositorios de las gestiones (tablas de trámites con fecha, cliente y demás)."""
from db import refs
from db.repo import Repo, _like_escape
from models import BAF, CASIM, CATER, GASTOS, PORTA, REGULAR


class GestionRepo(Repo):
    """Como Repo, pero sin código: ordena por fecha y trae el texto de los campos `select`."""

    def __init__(self, table, fields, filter_key):
        super().__init__(table, fields, filter_key)
        self.selects = [f for f in fields if f.kind == "select"]
        self.filter_select = next((i for i, f in enumerate(self.selects) if f.key == filter_key), None)

    def _get(self, row_id):
        return dict(self._db.execute(f"SELECT * FROM {self.table} WHERE id = ?", (row_id,)).fetchone())

    def distinct(self, key):
        """Valores del filtro. Si es un campo `select`, el texto de los registros elegidos."""
        if self.filter_select is None:
            return super().distinct(key)
        ref = self.selects[self.filter_select].ref
        sql = (f"SELECT DISTINCT {refs.label_sql(ref, 'r')} AS label FROM {self.table} g "
               f"JOIN {ref} r ON r.id = g.{key} WHERE g.activo = 1 ORDER BY label")
        return [r[0] for r in self._db.execute(sql)]

    def list(self, search="", filter_value=None):
        joins = "".join(f" LEFT JOIN {f.ref} r{i} ON r{i}.id = g.{f.key}" for i, f in enumerate(self.selects))
        labels = "".join(f", {refs.label_sql(f.ref, f'r{i}')} AS {f.key}_label" for i, f in enumerate(self.selects))
        searchable = [f"g.{k}" for k in self.text_keys]
        for i, f in enumerate(self.selects):
            searchable += refs.search_columns(f.ref, f"r{i}")
        where, params = ["g.activo = 1"], []
        for token in search.upper().split():
            where.append("(" + " OR ".join(f"{c} LIKE ? ESCAPE '\\'" for c in searchable) + ")")
            params += [f"%{_like_escape(token)}%"] * len(searchable)
        if filter_value:
            if self.filter_select is None:
                where.append(f"g.{self.filter_key} = ?")
            else:
                ref = self.selects[self.filter_select].ref
                where.append(f"{refs.label_sql(ref, f'r{self.filter_select}')} = ?")
            params.append(filter_value)
        sql = (f"SELECT g.*{labels} FROM {self.table} g{joins} "
               f"WHERE {' AND '.join(where)} ORDER BY g.fecha DESC, g.id DESC")
        return [dict(r) for r in self._db.execute(sql, params)]


class GestionVentaRepo(GestionRepo):
    """Gestión que vende un producto del stock: cada una genera un movimiento de VENTA.

    El movimiento (1 unidad del producto, al monto de la gestión) se guarda en la misma
    transacción, y su id queda en `mov_id`. Editar o dar de baja la gestión lo actualiza
    o lo revierte, con su efecto en el stock. Lo ve Stock > Movimientos.
    Regular y Porta no cobran: su movimiento es el de la SIM que entregan, a precio 0.
    Si tiene un campo `pagos`, los pagos (medio y monto) van a la tabla `pagos`, ligados a ese
    movimiento; cada fila trae `pagos` como [(id de cuenta, monto, código de la cuenta)].
    """

    def __init__(self, table, fields, filter_key, producto_key, movimientos, origen, numero_key="numero"):
        super().__init__(table, fields, filter_key)
        self.numero_key = numero_key   # el campo con el número de la línea, para la observación del movimiento
        self.con_pagos = any(f.kind == "pagos" for f in fields)
        self.producto_key = producto_key
        self.movimientos = movimientos   # nombre del repo en db.movimientos
        self.origen = origen

    @property
    def mov(self):
        from db import movimientos   # acá para evitar importaciones circulares
        return getattr(movimientos, self.movimientos)

    def list(self, search="", filter_value=None):
        rows = super().list(search, filter_value)
        if self.con_pagos:
            por_mov = {}
            for r in self._db.execute("SELECT p.mov_id, p.cuenta_id, p.monto, c.codigo FROM pagos p "
                                      "JOIN cuentas c ON c.id = p.cuenta_id WHERE p.origen = ? ORDER BY p.id",
                                      (self.mov.table,)):
                por_mov.setdefault(r["mov_id"], []).append((r["cuenta_id"], r["monto"], r["codigo"]))
            for row in rows:
                row["pagos"] = por_mov.get(row["mov_id"], [])
        return rows

    def _guardar_pagos(self, mov_id, data):
        if not self.con_pagos:
            return
        self._db.execute("DELETE FROM pagos WHERE origen = ? AND mov_id = ?", (self.mov.table, mov_id))
        self._db.executemany("INSERT INTO pagos (origen, mov_id, cuenta_id, monto) VALUES (?, ?, ?, ?)",
                             [(self.mov.table, mov_id, cuenta_id, monto) for cuenta_id, monto in data["pagos"]])

    def _mov_data(self, data):
        cuentas = {cuenta_id for cuenta_id, _ in data.get("pagos", [])}
        medio = ""   # con una sola cuenta, su código; con varias, el detalle está en `pagos`
        if len(cuentas) == 1:
            medio = self._db.execute("SELECT codigo FROM cuentas WHERE id = ?", (cuentas.pop(),)).fetchone()[0]
        obs = f"{self.origen} {data[self.numero_key]}" + (f" · IMEI {data['imei']}" if data.get("imei") else "")
        return {"fecha": data["fecha"], "tipo": "VENTA", "producto_id": data[self.producto_key],
                "cantidad": 1, "precio": data.get("monto", 0.0), "cliente": data["nombre"], "medio": medio,
                "vendedor_id": data["vendedor_id"], "sucursal_id": data["sucursal_id"],
                "cupon": "", "factura": "", "observaciones": obs,
                "imei": data.get("imei", "")}   # el movimiento de equipos da de baja ese IMEI de los cargados

    def _vincular(self, row_id, data):
        mov_id = self.mov._insert_con_stock(self._mov_data(data))
        self._db.execute(f"UPDATE {self.table} SET mov_id = ? WHERE id = ?", (mov_id, row_id))
        return mov_id

    def _mov_vigente(self, anterior):
        """El movimiento de la gestión, si existe y sigue activo (las gestiones viejas no lo tienen)."""
        if anterior["mov_id"] is None:
            return None
        mov = self.mov._get(anterior["mov_id"])
        return mov if mov["activo"] else None

    def check_imei(self, data, anterior=None):
        """Error si el IMEI de la gestión no se puede tomar de los cargados (ver MovimientoRepo.check_imei)."""
        mov_id = anterior["mov_id"] if anterior and self._mov_vigente(anterior) else None
        return self.mov.check_imei(self._mov_data(data), mov_id)

    def stock_despues(self, data, anterior=None):
        """(stock hoy, stock resultante, sin_stock) si se guardara `data` en lugar de la gestión `anterior`."""
        return self.mov.stock_despues(self._mov_data(data), self._mov_vigente(anterior) if anterior else None)

    def insert(self, data):
        with self._db:
            row_id = self._insert_row(data)
            self._guardar_pagos(self._vincular(row_id, data), data)
        return row_id

    def update(self, row_id, data):
        anterior = self._get(row_id)
        with self._db:
            self._update_row(row_id, data)
            if self._mov_vigente(anterior):
                mov_id = anterior["mov_id"]
                self.mov._update_con_stock(mov_id, self._mov_data(data))
            else:
                mov_id = self._vincular(row_id, data)
            self._guardar_pagos(mov_id, data)

    def deactivate(self, row_id):
        anterior = self._get(row_id)
        with self._db:
            if self._mov_vigente(anterior):
                self.mov._deactivate_con_stock(anterior["mov_id"])
            self._deactivate_row(row_id)


casim = GestionVentaRepo("casim", CASIM, "vendedor_id", "sim_id", "mov_equipos", "CASIM")
cater = GestionVentaRepo("cater", CATER, "vendedor_id", "equipo_id", "mov_equipos", "CATER")
regular = GestionVentaRepo("regular", REGULAR, "vendedor_id", "sim_id", "mov_equipos", "REGULAR")
porta = GestionVentaRepo("porta", PORTA, "vendedor_id", "sim_id", "mov_equipos", "PORTA", numero_key="numero_portar")
baf = GestionRepo("baf", BAF, filter_key="estado")
gastos = GestionRepo("gastos", GASTOS, filter_key="vendedor_id")
