"""Conexión única a SQLite y creación del esquema."""
import os
import sqlite3
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "nodo.db"

# IMEI de los equipos: una fila por unidad. No mueve stock (el stock se mueve en los movimientos).
IMEIS_DDL = """
CREATE TABLE IF NOT EXISTS imeis (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id     INTEGER NOT NULL REFERENCES equipos(id),
    imei          TEXT    NOT NULL UNIQUE,             -- 15 dígitos
    sucursal_id   INTEGER REFERENCES sucursales(id),   -- dónde está la unidad
    fecha_ingreso TEXT    NOT NULL DEFAULT (date('now', 'localtime')),   -- AAAA-MM-DD: de acá sale la antigüedad
    activo        INTEGER NOT NULL DEFAULT 1,          -- 0 = quitado o vendido
    salida        TEXT    NOT NULL DEFAULT '',         -- venta que lo sacó ("tabla:id"); vacío = quitado a mano
    remito        TEXT    NOT NULL DEFAULT ''          -- pedido / remito con el que ingresó
);
"""

SCHEMA = """
CREATE TABLE IF NOT EXISTS accesorios (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo           TEXT    NOT NULL UNIQUE,
    categoria        TEXT    NOT NULL DEFAULT '',
    descripcion      TEXT    NOT NULL,
    precio_mayorista REAL    NOT NULL DEFAULT 0,
    precio_minorista REAL    NOT NULL DEFAULT 0,
    stock            INTEGER NOT NULL DEFAULT 0,
    virtual          INTEGER NOT NULL DEFAULT 0,  -- 1 = producto virtual: no maneja stock
    activo           INTEGER NOT NULL DEFAULT 1   -- 0 = dado de baja (borrado lógico)
);

CREATE TABLE IF NOT EXISTS equipos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT    NOT NULL UNIQUE,
    descripcion TEXT    NOT NULL,
    marca       TEXT    NOT NULL DEFAULT '',   -- "SIM" para los chips: no son un accesorio, Claro los manda con los equipos
    modelo      TEXT    NOT NULL DEFAULT '',
    rom         TEXT    NOT NULL DEFAULT '',
    ram         TEXT    NOT NULL DEFAULT '',
    color       TEXT    NOT NULL DEFAULT '',
    precio      REAL    NOT NULL DEFAULT 0,  -- precio sugerido: orientativo, en la venta se puede cambiar
    stock       INTEGER NOT NULL DEFAULT 0,
    virtual     INTEGER NOT NULL DEFAULT 0,  -- 1 = no lleva stock (la E-SIM)
    activo      INTEGER NOT NULL DEFAULT 1
);
"""

# CaSIM, Regular y Porta: sim_id apunta a un equipo (marca "SIM"), no a un accesorio. Sin IMEI: la sucursal no
# las entrega en orden y varias se pierden o se mezclan, así que no vale la pena cargar un número de serie por
# unidad (a diferencia de un equipo de verdad). Van en constantes propias porque SQLite no permite cambiar el
# REFERENCES de una columna existente: la migración que las trae de Accesorios reconstruye la tabla con esta
# misma definición (ver _m7_chips_a_equipos).
CASIM_DDL = """
CREATE TABLE IF NOT EXISTS casim (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    nombre        TEXT    NOT NULL,
    numero        TEXT    NOT NULL,
    sim_id        INTEGER NOT NULL REFERENCES equipos(id),
    monto         REAL    NOT NULL DEFAULT 0,
    cuenta_id     INTEGER REFERENCES cuentas(id),
    vendedor_id   INTEGER REFERENCES empleados(id),
    sucursal_id   INTEGER REFERENCES sucursales(id),
    mov_id        INTEGER,                     -- movimiento de VENTA que generó (mov_equipos)
    observaciones TEXT    NOT NULL DEFAULT '',
    activo        INTEGER NOT NULL DEFAULT 1
);
"""
SCHEMA += CASIM_DDL

SCHEMA += """
CREATE TABLE IF NOT EXISTS cater (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    nombre        TEXT    NOT NULL,
    numero        TEXT    NOT NULL,
    equipo_id     INTEGER NOT NULL REFERENCES equipos(id),
    imei          TEXT    NOT NULL DEFAULT '',
    monto         REAL    NOT NULL DEFAULT 0,
    vendedor_id   INTEGER REFERENCES empleados(id),
    sucursal_id   INTEGER REFERENCES sucursales(id),
    mov_id        INTEGER,                     -- movimiento de VENTA que generó (mov_accesorios / mov_equipos)
    observaciones TEXT    NOT NULL DEFAULT '',
    activo        INTEGER NOT NULL DEFAULT 1
);

-- Venta de accesorios con varios productos (Nuevo > Accesorios): cada producto es un movimiento VENTA de
-- mov_accesorios (con venta_id) y sus pagos van a `pagos` con origen = 'ventas' y mov_id = el id de la venta.
CREATE TABLE IF NOT EXISTS ventas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    cliente       TEXT    NOT NULL DEFAULT '',
    vendedor_id   INTEGER REFERENCES empleados(id),
    sucursal_id   INTEGER NOT NULL REFERENCES sucursales(id),
    cupon         TEXT    NOT NULL DEFAULT '',
    factura       TEXT    NOT NULL DEFAULT '',
    observaciones TEXT    NOT NULL DEFAULT '',
    activo        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS gastos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    detalle       TEXT    NOT NULL,
    factura       TEXT    NOT NULL DEFAULT '',
    monto         REAL    NOT NULL DEFAULT 0,          -- siempre positivo: la caja lo muestra restando
    cuenta_id     INTEGER REFERENCES cuentas(id),
    vendedor_id   INTEGER REFERENCES empleados(id),
    sucursal_id   INTEGER REFERENCES sucursales(id),
    observaciones TEXT    NOT NULL DEFAULT '',
    activo        INTEGER NOT NULL DEFAULT 1
);

-- Arqueo de caja (Caja > Arqueo de caja, traído de MyTools): lo que hay en la caja fuerte (CF) y en la caja chica (CC)
-- contra el saldo que dice el sistema (SS). resultado = CF + CC - SS: positivo sobra, negativo falta, y se arrastra de
-- un arqueo al siguiente (la variación de cada uno es su resultado menos el del arqueo anterior).
-- Cada monto guarda lo que se escribió (cf_expr: "700.000+100.000") y su suma (cf_val).
CREATE TABLE IF NOT EXISTS arqueos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    cf_expr   TEXT NOT NULL DEFAULT '0',
    cf_val    REAL NOT NULL DEFAULT 0,
    cc_expr   TEXT NOT NULL DEFAULT '0',
    cc_val    REAL NOT NULL DEFAULT 0,
    sc_expr   TEXT NOT NULL DEFAULT '0',
    sc_val    REAL NOT NULL DEFAULT 0,
    resultado REAL NOT NULL DEFAULT 0,
    activo    INTEGER NOT NULL DEFAULT 1
);

-- Quiénes hicieron el arqueo: el nombre tal como estaba en ese momento (no cambia si después se renombra al empleado)
CREATE TABLE IF NOT EXISTS arqueo_empleados (
    arqueo_id INTEGER NOT NULL REFERENCES arqueos(id),
    nombre    TEXT    NOT NULL
);

-- Datos sueltos de la app (p. ej. cuándo se hizo la última copia de seguridad)
CREATE TABLE IF NOT EXISTS ajustes (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS planes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS descuentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL UNIQUE,
    descripcion TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);
"""

REGULAR_DDL = """
CREATE TABLE IF NOT EXISTS regular (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    nombre        TEXT    NOT NULL,
    telefono      TEXT    NOT NULL DEFAULT '',   -- de contacto (opcional)
    documento     TEXT    NOT NULL,              -- DNI o CUIT
    plan_id       INTEGER NOT NULL REFERENCES planes(id),
    descuento_id  INTEGER REFERENCES descuentos(id),
    numero        TEXT    NOT NULL,              -- el número nuevo
    id_gestion    TEXT    NOT NULL,              -- 9 dígitos
    vendedor_id   INTEGER REFERENCES empleados(id),
    sim_id        INTEGER REFERENCES equipos(id),   -- la SIM que se entrega: descuenta stock
    sucursal_id   INTEGER REFERENCES sucursales(id),
    mov_id        INTEGER,                             -- movimiento de VENTA de la SIM (mov_equipos)
    observaciones TEXT    NOT NULL DEFAULT '',
    activo        INTEGER NOT NULL DEFAULT 1
);
"""
SCHEMA += REGULAR_DDL

PORTA_DDL = """
CREATE TABLE IF NOT EXISTS porta (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    nombre        TEXT    NOT NULL,
    numero_portar TEXT    NOT NULL,              -- el número que se porta
    compania_donante TEXT NOT NULL DEFAULT '',   -- de qué compañía viene
    tipo_negocio  TEXT    NOT NULL DEFAULT '',   -- PREPAGO | POSPAGO (el que tenía)
    documento     TEXT    NOT NULL DEFAULT '',   -- DNI o CUIT (opcional)
    plan_id       INTEGER NOT NULL REFERENCES planes(id),
    descuento_id  INTEGER REFERENCES descuentos(id),
    nim           TEXT    NOT NULL,              -- NIM temporal
    pin           TEXT    NOT NULL DEFAULT '',   -- PIN ingresado durante la portabilidad
    fecha_portacion TEXT  NOT NULL DEFAULT '',   -- AAAA-MM-DD o vacío
    id_gestion    TEXT    NOT NULL,              -- 9 dígitos
    vendedor_id   INTEGER REFERENCES empleados(id),
    sim_id        INTEGER REFERENCES equipos(id),   -- la SIM que se entrega: descuenta stock
    sucursal_id   INTEGER REFERENCES sucursales(id),
    mov_id        INTEGER,                             -- movimiento de VENTA de la SIM (mov_equipos)
    observaciones TEXT    NOT NULL DEFAULT '',
    activo        INTEGER NOT NULL DEFAULT 1
);
"""
SCHEMA += PORTA_DDL

SCHEMA += """
CREATE TABLE IF NOT EXISTS planes_baf (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL UNIQUE,      -- p. ej. 500MB
    descripcion TEXT NOT NULL,
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS baf (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha             TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),   -- fecha de ingreso
    vendedor_id       INTEGER NOT NULL REFERENCES empleados(id),
    nombre            TEXT    NOT NULL,                                          -- titular
    documento         TEXT    NOT NULL DEFAULT '',
    fecha_nacimiento  TEXT    NOT NULL DEFAULT '',                               -- AAAA-MM-DD o vacío
    email             TEXT    NOT NULL DEFAULT '',
    telefono          TEXT    NOT NULL,
    telefono_alt      TEXT    NOT NULL DEFAULT '',
    localidad         TEXT    NOT NULL,
    calle             TEXT    NOT NULL,
    altura            TEXT    NOT NULL,
    entre_calles      TEXT    NOT NULL DEFAULT '',
    torre_piso_depto  TEXT    NOT NULL DEFAULT '',
    tipo_domicilio    TEXT    NOT NULL,                                          -- Casa | Edificio | Pasillo | Empresa
    plan_id           INTEGER REFERENCES planes_baf(id),
    cantidad_tv       TEXT    NOT NULL DEFAULT '',                               -- N/A | 1 | 2 | 3
    fecha_pactada     TEXT    NOT NULL DEFAULT '',
    franja            TEXT    NOT NULL DEFAULT '',                               -- AM | PM
    ot                TEXT    NOT NULL DEFAULT '',
    sds               TEXT    NOT NULL DEFAULT '',
    fecha_instalacion TEXT    NOT NULL DEFAULT '',
    estado            TEXT    NOT NULL DEFAULT '',
    con_form          INTEGER NOT NULL DEFAULT 0,                                -- 1 = cargado en el formulario de Claro
    observaciones     TEXT    NOT NULL DEFAULT '',
    activo            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sucursales (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL UNIQUE,      -- nombre clave: tipo + número (A001, L002...); el nombre legible va en `nombre`
    entidad     TEXT NOT NULL DEFAULT '',
    nombre      TEXT NOT NULL,
    calle       TEXT NOT NULL DEFAULT '',
    numero      TEXT NOT NULL DEFAULT '',
    piso_depto  TEXT NOT NULL DEFAULT '',
    telefono    TEXT NOT NULL DEFAULT '',
    ciudad      TEXT NOT NULL DEFAULT '',
    cp          TEXT NOT NULL DEFAULT '',
    provincia   TEXT NOT NULL DEFAULT '',
    responsable TEXT NOT NULL DEFAULT '',
    celular     TEXT NOT NULL DEFAULT '',
    activo      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS empleados (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL,
    rol     TEXT NOT NULL DEFAULT '',                  -- cargo
    celular TEXT NOT NULL DEFAULT '',                  -- teléfono
    email   TEXT NOT NULL DEFAULT '',
    fecha_nacimiento TEXT NOT NULL DEFAULT '',         -- AAAA-MM-DD o vacío
    activo  INTEGER NOT NULL DEFAULT 1
);

-- un empleado puede estar asignado a una o varias sucursales
CREATE TABLE IF NOT EXISTS empleado_sucursal (
    empleado_id INTEGER NOT NULL REFERENCES empleados(id),
    sucursal_id INTEGER NOT NULL REFERENCES sucursales(id),
    PRIMARY KEY (empleado_id, sucursal_id)
);

CREATE TABLE IF NOT EXISTS cuentas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo        TEXT NOT NULL UNIQUE,
    tipo          TEXT NOT NULL,
    descripcion   TEXT NOT NULL,
    saldo_inicial REAL NOT NULL DEFAULT 0,
    activo        INTEGER NOT NULL DEFAULT 1
);

-- Días que el local no abre (feriados, balance...), para la proyección mensual de Estadísticas.
CREATE TABLE IF NOT EXISTS cierres (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha  TEXT    NOT NULL UNIQUE,
    motivo TEXT    NOT NULL DEFAULT '',
    activo INTEGER NOT NULL DEFAULT 1
);
"""

# Movimientos de stock: una tabla por tipo de producto, con el mismo formato.
_MOVIMIENTOS = """
CREATE TABLE IF NOT EXISTS {tabla} (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha         TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    tipo          TEXT    NOT NULL,            -- INGRESO | VENTA | CONCILIACION
    producto_id   INTEGER NOT NULL REFERENCES {producto}(id),
    cantidad      INTEGER NOT NULL,            -- con signo solo en CONCILIACION (ajuste)
    precio        REAL    NOT NULL DEFAULT 0,
    cliente       TEXT    NOT NULL DEFAULT '',
    medio         TEXT    NOT NULL DEFAULT '', -- EFE, VISA, MASTER... (solo ventas)
    vendedor_id   INTEGER REFERENCES empleados(id),
    sucursal_id   INTEGER NOT NULL REFERENCES sucursales(id),
    cupon         TEXT    NOT NULL DEFAULT '',
{imei}    factura       TEXT    NOT NULL DEFAULT '',
    observaciones TEXT    NOT NULL DEFAULT '',
{venta}    activo        INTEGER NOT NULL DEFAULT 1
);
"""
SCHEMA += _MOVIMIENTOS.format(tabla="mov_accesorios", producto="accesorios", imei="",
                              venta="    venta_id      INTEGER REFERENCES ventas(id),  -- venta de Nuevo > Accesorios a la que pertenece\n")
SCHEMA += _MOVIMIENTOS.format(tabla="mov_equipos", producto="equipos", venta="",
                              imei="    imei          TEXT    NOT NULL DEFAULT '',            -- de la unidad vendida (equipos)\n")

SCHEMA += IMEIS_DDL

# Pagos de una venta (puede haber varios, cada uno a una Cuenta: EFE, VISA, FINANCIADO...).
# `origen` es la tabla del movimiento (mov_accesorios / mov_equipos) o 'ventas', y `mov_id` su id.
# `monto` es la parte de la venta que cubre el pago; `interes`, lo que el posnet cobró de más por las cuotas
# (lo calcula el posnet: se carga aparte para que la caja lo diferencie de la venta).
SCHEMA += """
CREATE TABLE IF NOT EXISTS pagos (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    origen TEXT    NOT NULL,
    mov_id INTEGER NOT NULL,
    cuenta_id INTEGER NOT NULL REFERENCES cuentas(id),
    monto  REAL    NOT NULL,
    interes REAL   NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS pagos_mov ON pagos (origen, mov_id);
"""

_conn = None


# --- Migraciones --------------------------------------------------------------------------------
# La versión de la base se guarda dentro del propio archivo (PRAGMA user_version). Al abrir, se aplican
# en orden las migraciones de MIGRACIONES cuyo número (posición + 1) es mayor a esa versión. Cada una corre
# en su propia transacción junto con el cambio de versión: si falla, la base queda como estaba.
#
# SCHEMA describe siempre la última versión. Una base nueva se crea con SCHEMA y arranca ya en la última
# versión, sin correr ninguna migración. Para cambiar el esquema:
#   1. actualizar SCHEMA;
#   2. agregar AL FINAL de MIGRACIONES una función que lleve una base existente de la versión anterior a la nueva
#      (no editar ni reordenar las que ya están: hay bases que ya las pasaron);
#   3. si hace falta un índice sobre una columna nueva, crearlo en la migración, no en SCHEMA (SCHEMA se ejecuta
#      antes de migrar, y en una base vieja esa columna todavía no existe).
# Las funciones no confirman la transacción (nada de `with conn:` ni conn.commit()): lo hace _migrar.

def _columnas(conn, tabla):
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({tabla})")]


def _sembrar_planes_baf(conn):
    """Los planes de fibra vigentes, si la tabla está vacía."""
    if not conn.execute("SELECT 1 FROM planes_baf").fetchone():
        conn.executemany("INSERT INTO planes_baf (codigo, descripcion) VALUES (?, ?)",
                         [("200MB", "FIBRA 200 MB"), ("500MB", "FIBRA 500 MB"), ("800MB", "FIBRA 800 MB")])


def _migrar_planes(conn):
    """Los planes eran REGULAR o PORTA; son los mismos para todas las gestiones, así que no llevan tipo."""
    if "tipo" in _columnas(conn, "planes"):
        conn.execute("ALTER TABLE planes DROP COLUMN tipo")


def _migrar_pagos(conn):
    """Pagos y CaTER creados cuando el pago era un medio de texto: ahora es una Cuenta."""
    if "cuenta_id" not in _columnas(conn, "pagos"):
        conn.execute("ALTER TABLE pagos ADD COLUMN cuenta_id INTEGER REFERENCES cuentas(id)")
        conn.execute("UPDATE pagos SET cuenta_id = (SELECT id FROM cuentas c WHERE c.codigo = pagos.medio "
                     "AND c.activo = 1 LIMIT 1)")
        conn.execute("DELETE FROM pagos WHERE cuenta_id IS NULL")   # medios que no son una Cuenta
        conn.execute("ALTER TABLE pagos DROP COLUMN medio")
    if "cuenta_id" in _columnas(conn, "cater") and \
            not conn.execute("SELECT 1 FROM cater WHERE cuenta_id IS NOT NULL").fetchone():
        # CaTER ya no tiene un campo Cuenta aparte: la cuenta va en cada pago
        conn.execute("ALTER TABLE cater DROP COLUMN cuenta_id")


def _migrar_gestion(conn, tabla):
    """Gestiones creadas cuando vendedor y cuenta eran texto: pasan a apuntar a Empleados y Cuentas."""
    if "vendedor_id" in _columnas(conn, tabla):
        return
    for col, ref in (("vendedor_id", "empleados"), ("cuenta_id", "cuentas"), ("sucursal_id", "sucursales")):
        conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} INTEGER REFERENCES {ref}(id)")
    conn.execute(f"ALTER TABLE {tabla} ADD COLUMN mov_id INTEGER")
    conn.execute(f"UPDATE {tabla} SET vendedor_id = (SELECT id FROM empleados e "
                 f"WHERE e.nombre = {tabla}.vendedor AND e.activo = 1 LIMIT 1) WHERE vendedor <> ''")
    conn.execute(f"UPDATE {tabla} SET cuenta_id = (SELECT id FROM cuentas c "
                 f"WHERE c.codigo = {tabla}.cuenta AND c.activo = 1 LIMIT 1) WHERE cuenta <> ''")
    conn.execute(f"ALTER TABLE {tabla} DROP COLUMN vendedor")
    conn.execute(f"ALTER TABLE {tabla} DROP COLUMN cuenta")


def _m1_bases_anteriores_al_control_de_version(conn):
    """Todo lo que se fue agregando antes de que existiera user_version. Cada paso revisa si ya está hecho,
    así que es seguro correrlo sobre una base que ya tenía algunos de esos cambios."""
    _sembrar_planes_baf(conn)
    if "virtual" not in _columnas(conn, "accesorios"):
        conn.execute("ALTER TABLE accesorios ADD COLUMN virtual INTEGER NOT NULL DEFAULT 0")
    if "precio" not in _columnas(conn, "equipos"):
        conn.execute("ALTER TABLE equipos ADD COLUMN precio REAL NOT NULL DEFAULT 0")
    for tabla in ("casim", "cater"):
        _migrar_gestion(conn, tabla)
    for tabla, columna, ddl in (("porta", "pin", "TEXT NOT NULL DEFAULT ''"),
                                ("imeis", "salida", "TEXT NOT NULL DEFAULT ''"),
                                ("imeis", "remito", "TEXT NOT NULL DEFAULT ''"),
                                ("mov_equipos", "imei", "TEXT NOT NULL DEFAULT ''"),
                                ("porta", "compania_donante", "TEXT NOT NULL DEFAULT ''"),
                                ("porta", "tipo_negocio", "TEXT NOT NULL DEFAULT ''")):
        if columna not in _columnas(conn, tabla):
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {ddl}")
    _migrar_pagos(conn)
    _migrar_planes(conn)


def _m2_pagos_de_ventas_dadas_de_baja(conn):
    """Dar de baja una venta dejaba sus pagos en la tabla, y un total de caja los habría contado.
    Ahora se borran junto con la baja (db/movimientos.py); acá se limpian los que hayan quedado."""
    for tabla in ("mov_accesorios", "mov_equipos"):
        conn.execute(f"DELETE FROM pagos WHERE origen = ? "
                     f"AND mov_id NOT IN (SELECT id FROM {tabla} WHERE activo = 1)", (tabla,))


def _m3_ventas_con_varios_productos_e_intereses(conn):
    """Las tablas nuevas (ventas, gastos) las crea SCHEMA; acá van las columnas nuevas de tablas que ya existían."""
    if "venta_id" not in _columnas(conn, "mov_accesorios"):
        conn.execute("ALTER TABLE mov_accesorios ADD COLUMN venta_id INTEGER REFERENCES ventas(id)")
    if "interes" not in _columnas(conn, "pagos"):
        conn.execute("ALTER TABLE pagos ADD COLUMN interes REAL NOT NULL DEFAULT 0")


def _m4_regular_y_porta_descuentan_sim(conn):
    """Regular y Porta entregan una SIM (descuenta stock, como CaSIM): tipo de SIM, sucursal y el movimiento generado.
    Las filas que ya existían quedan sin esos datos: se completan editándolas."""
    for tabla in ("regular", "porta"):
        for columna, ddl in (("sim_id", "INTEGER REFERENCES accesorios(id)"),
                             ("sucursal_id", "INTEGER REFERENCES sucursales(id)"), ("mov_id", "INTEGER")):
            if columna not in _columnas(conn, tabla):
                conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {ddl}")


def _m5_empleados_mail_y_nacimiento(conn):
    for columna in ("email", "fecha_nacimiento"):
        if columna not in _columnas(conn, "empleados"):
            conn.execute(f"ALTER TABLE empleados ADD COLUMN {columna} TEXT NOT NULL DEFAULT ''")


def _m6_porta_fecha_portacion(conn):
    if "fecha_portacion" not in _columnas(conn, "porta"):
        conn.execute("ALTER TABLE porta ADD COLUMN fecha_portacion TEXT NOT NULL DEFAULT ''")


def _m7_chips_a_equipos(conn):
    """Los chips (SIM física y E-SIM) pasan de Accesorios a Equipos, sin IMEI: no son un accesorio como tal,
    y Claro también los manda en el mismo pedido que los equipos. CaSIM, Regular y Porta ahora entregan un
    equipo (marca "SIM") en vez de un accesorio: sim_id pasa a apuntar a equipos, y su movimiento de VENTA
    pasa de mov_accesorios a mov_equipos (se mueve tal cual: misma fecha, cantidad, medio de cobro...).
    Ninguno tenía venta_id ni pagos propios (se comprobó antes de escribir esta migración), así que no hay
    nada que se pierda en el pase. Los accesorios viejos quedan dados de baja, no se borran."""
    if "virtual" not in _columnas(conn, "equipos"):
        conn.execute("ALTER TABLE equipos ADD COLUMN virtual INTEGER NOT NULL DEFAULT 0")
    chips = conn.execute("SELECT id, codigo, descripcion, stock, virtual FROM accesorios "
                         "WHERE categoria = 'SIMS' AND activo = 1").fetchall()
    if not chips:
        return   # base nueva (ya nace con SCHEMA al día), o esta migración ya corrió
    equivalencia = {}   # id de accesorios -> id de equipos
    for id_acc, codigo, descripcion, stock, virtual in chips:
        existente = conn.execute("SELECT id FROM equipos WHERE codigo = ?", (codigo,)).fetchone()
        if existente:   # el código ya está de otra vez (dado de baja o no): se reactiva y se completa
            id_eq = existente[0]
            conn.execute("UPDATE equipos SET descripcion = ?, marca = 'SIM', stock = ?, virtual = ?, activo = 1 "
                        "WHERE id = ?", (descripcion, stock, virtual, id_eq))
        else:
            cur = conn.execute("INSERT INTO equipos (codigo, descripcion, marca, stock, virtual) "
                               "VALUES (?, ?, 'SIM', ?, ?)", (codigo, descripcion, stock, virtual))
            id_eq = cur.lastrowid
        equivalencia[id_acc] = id_eq

    # sim_id apuntaba a accesorios: SQLite no permite cambiar el REFERENCES de una columna existente, así que
    # cada tabla se reconstruye con la definición nueva (CASIM_DDL / REGULAR_DDL / PORTA_DDL, ya con sim_id
    # REFERENCES equipos) y se reescribe sim_id de paso.
    for tabla, ddl in (("casim", CASIM_DDL), ("regular", REGULAR_DDL), ("porta", PORTA_DDL)):
        columnas = _columnas(conn, tabla)
        casos = " ".join(f"WHEN sim_id = {viejo} THEN {nuevo}" for viejo, nuevo in equivalencia.items())
        select = ", ".join(f"CASE {casos} ELSE sim_id END" if c == "sim_id" else c for c in columnas)
        conn.execute(f"ALTER TABLE {tabla} RENAME TO {tabla}_viejo")
        conn.execute(ddl)
        conn.execute(f"INSERT INTO {tabla} ({', '.join(columnas)}) SELECT {select} FROM {tabla}_viejo")
        conn.execute(f"DROP TABLE {tabla}_viejo")

    # los movimientos de esos chips pasan de mov_accesorios a mov_equipos
    mov_equivalencia = {}   # id de mov_accesorios -> id de mov_equipos
    for id_acc, id_eq in equivalencia.items():
        movs = conn.execute("SELECT id, fecha, tipo, cantidad, precio, cliente, medio, vendedor_id, "
                            "sucursal_id, cupon, factura, observaciones, activo FROM mov_accesorios "
                            "WHERE producto_id = ?", (id_acc,)).fetchall()
        for (mov_id, fecha, tipo, cantidad, precio, cliente, medio, vendedor_id, sucursal_id, cupon, factura,
             observaciones, activo) in movs:
            cur = conn.execute(
                "INSERT INTO mov_equipos (fecha, tipo, producto_id, cantidad, precio, cliente, medio, "
                "vendedor_id, sucursal_id, cupon, factura, observaciones, activo, imei) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')",
                (fecha, tipo, id_eq, cantidad, precio, cliente, medio, vendedor_id, sucursal_id, cupon,
                 factura, observaciones, activo))
            mov_equivalencia[mov_id] = cur.lastrowid
        conn.execute("DELETE FROM mov_accesorios WHERE producto_id = ?", (id_acc,))

    for tabla in ("casim", "regular", "porta"):
        for row_id, mov_id in conn.execute(f"SELECT id, mov_id FROM {tabla} WHERE mov_id IS NOT NULL").fetchall():
            nuevo = mov_equivalencia.get(mov_id)
            if nuevo is not None:
                conn.execute(f"UPDATE {tabla} SET mov_id = ? WHERE id = ?", (nuevo, row_id))

    conn.execute(f"UPDATE accesorios SET activo = 0 WHERE id IN ({', '.join('?' * len(equivalencia))})",
                list(equivalencia))


MIGRACIONES = [_m1_bases_anteriores_al_control_de_version, _m2_pagos_de_ventas_dadas_de_baja,
               _m3_ventas_con_varios_productos_e_intereses, _m4_regular_y_porta_descuentan_sim,
               _m5_empleados_mail_y_nacimiento, _m6_porta_fecha_portacion, _m7_chips_a_equipos]


def _migrar(conn):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(MIGRACIONES):
        raise RuntimeError(f"La base es de una versión más nueva ({version}) que la de esta copia de Nodo "
                           f"({len(MIGRACIONES)}): actualizá la app en vez de abrirla con esta.")
    for numero in range(version + 1, len(MIGRACIONES) + 1):
        try:
            conn.execute("BEGIN")
            MIGRACIONES[numero - 1](conn)
            conn.execute(f"PRAGMA user_version = {numero}")
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def get():
    """Devuelve la conexión, creándola (y el esquema) la primera vez.

    La variable de entorno NODO_DB permite apuntar a otro archivo (pruebas).
    """
    global _conn
    if _conn is None:
        path = Path(os.environ.get("NODO_DB", DEFAULT_PATH))
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        # Sin esto SQLite ignora los REFERENCES: hay que pedirlo en cada conexión.
        conn.execute("PRAGMA foreign_keys = ON")
        base_nueva = not conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table'").fetchone()
        conn.executescript(SCHEMA)
        if base_nueva:   # ya nace en la última versión
            with conn:
                _sembrar_planes_baf(conn)
                conn.execute(f"PRAGMA user_version = {len(MIGRACIONES)}")
        else:
            _migrar(conn)
        _conn = conn
    return _conn
