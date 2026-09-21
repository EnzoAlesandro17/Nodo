"""Definición de los campos de cada tabla. La usan tanto la base de datos como la UI.

`key` coincide con el nombre de la columna en SQLite.
`kind`: text | choice (texto con sugerencias de lo ya cargado) | money | int | bool | select | datetime | multi | list
(list = lista cerrada de textos fijos (`options`);
 multi = varias opciones de la tabla `ref`, en una tabla intermedia (no es columna);
 calc = columna calculada, solo se muestra en la tabla (no es columna ni entra en formularios ni CSV);
 date = fecha sin hora "AAAA-MM-DD" (puede quedar vacía), en el formulario dd/mm/aaaa;
 datetime = fecha y hora "AAAA-MM-DD HH:MM:SS", en el formulario dd/mm/aaaa hh:mm, precargada con la actual;
 bool = casilla 0/1 en el formulario, sin columna en la tabla;
 pagos = varios pagos [(id de la cuenta, monto)], cada uno con una Cuenta de la tabla `ref`, guardados
         en la tabla `pagos` (no es columna); `total` es el campo con el monto total, para mostrar cuánto falta;
 select = lista cerrada que guarda el id de un registro de la tabla `ref`)
"""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    kind: str = "text"
    required: bool = False
    width: int = 110        # ancho de columna en la tabla
    stretch: bool = False   # la columna absorbe el espacio sobrante
    disables: str = ""      # bool: al tildarlo se deshabilita (y pone en 0) este otro campo
    ref: str = ""           # select: tabla a la que apunta (se muestra su descripción)
    in_table: bool = True   # False: solo aparece en el formulario, no como columna de la tabla
    options: tuple = ()     # list: opciones permitidas
    default: str = ""       # valor inicial en un alta
    signed: bool = False    # int: acepta negativos
    digits: int | tuple = 0  # text: si > 0, tiene que ser un número de esa cantidad de dígitos (o de una de ellas)
    total: str = ""         # pagos: campo con el monto total a pagar
    suggests: str = ""      # select: al elegir un registro, propone su precio en este otro campo (si está vacío)


NUMERIC_KINDS = ("money", "int")

ACCESORIOS = (
    Field("codigo", "Código", required=True, width=110),
    Field("categoria", "Categoría", kind="choice", width=150),
    Field("descripcion", "Descripción", required=True, width=260, stretch=True),
    Field("precio_mayorista", "Precio mayorista", kind="money", width=130),
    Field("precio_minorista", "Precio minorista", kind="money", width=130),
    Field("stock", "Cantidad en stock", kind="int", width=130),
    Field("virtual", "Virtual (sin stock)", kind="bool", disables="stock"),
)

EQUIPOS = (
    Field("codigo", "Código", required=True, width=110),
    Field("descripcion", "Descripción", required=True, width=240, stretch=True),
    Field("marca", "Marca", kind="choice", width=120),
    Field("modelo", "Modelo", width=130),
    Field("rom", "ROM", width=80),
    Field("ram", "RAM", width=80),
    Field("color", "Color", width=100),
    Field("precio", "Precio sugerido", kind="money", width=110),
    Field("imeis", "IMEI", kind="calc", width=60),
    Field("dias", "Antig. máx. (días)", kind="calc", width=120),
    Field("stock", "Stock", kind="int", width=80),
)

MEDIOS_COBRO = ("EFE", "VISA", "MASTER", "MAESTRO", "AMEX", "NARANJA", "CONSUMAX", "QR")   # EFE = efectivo

# Gestiones (menú Nuevo > Gestiones). Cada una es una tabla propia con este formato.
CASIM = (
    Field("fecha", "Fecha y hora", kind="datetime", required=True, width=130),
    Field("nombre", "Nombre o Razón", required=True, width=140),
    Field("numero", "Número", required=True, width=100, digits=10),
    Field("sim_id", "Tipo de SIM", kind="select", required=True, width=160, ref="accesorios"),
    Field("monto", "Monto", kind="money", width=90),
    Field("cuenta_id", "Cuenta", kind="select", width=100, ref="cuentas"),
    Field("vendedor_id", "Vendedor", kind="select", width=100, ref="empleados"),
    Field("sucursal_id", "Sucursal", kind="select", required=True, width=100, ref="sucursales"),
    Field("observaciones", "Observaciones", width=150, stretch=True),
)

def _linea(numero_a, numero_b, tras_a=(), tras_b=()):
    """Regular y Porta: el mismo formato, cambian los dos números. Cada una descuenta una SIM del stock (como CaSIM).
    `numero_a` (key, label, obligatorio): el de contacto o el a portar; `numero_b`: el nuevo o el NIM temporal;
    `tras_a` y `tras_b`: campos propios de la gestión, a continuación de `numero_a` y de `numero_b`."""
    (ka, la, ra), (kb, lb, rb) = numero_a, numero_b
    return (
        Field("fecha", "Fecha y hora", kind="datetime", required=True, width=125),
        Field("nombre", "Nombre o Razón", required=True, width=140),
        Field(ka, la, required=ra, width=110, digits=10),
        *tras_a,
        Field("documento", "DNI / CUIT", width=100, digits=(7, 8, 11)),
        Field("plan_id", "Plan", kind="select", required=True, width=110, ref="planes"),
        Field("descuento_id", "Descuento", kind="select", width=110, ref="descuentos"),
        Field(kb, lb, required=rb, width=100, digits=10),
        *tras_b,
        Field("id_gestion", "ID de gestión", required=True, width=90, digits=9),
        Field("vendedor_id", "Vendedor", kind="select", width=100, ref="empleados"),
        Field("sim_id", "Tipo de SIM", kind="select", required=True, width=140, ref="accesorios", in_table=False),
        Field("sucursal_id", "Sucursal", kind="select", required=True, width=100, ref="sucursales", in_table=False),
        Field("observaciones", "Observaciones", width=140, stretch=True),
    )


REGULAR = _linea(("telefono", "Teléfono de contacto", False), ("numero", "Nuevo número", True))
COMPANIAS = ("PERSONAL", "MOVISTAR", "IMOWI")   # sugeridas: se puede escribir otra

PORTA = tuple(replace(f, in_table=False) if f.key == "documento" else f for f in _linea(
    ("numero_portar", "Número a portar", True), ("nim", "NIM temporal", True),
    tras_a=(Field("compania_donante", "Compañía donante", kind="choice", required=True, options=COMPANIAS, width=110),
            Field("tipo_negocio", "Tipo de negocio actual", kind="list", required=True,
                  options=("PREPAGO", "POSPAGO"), width=100)),
    tras_b=(Field("pin", "PIN de portabilidad", required=True, width=90),)))

# BAF (banda ancha fija = fibra óptica): venta e instalación, del titular al estado de la instalación.
ESTADOS_BAF = ("Deuda", "HP", "Falta pactar", "Pactada", "Cancelada", "Instalada")
TIPOS_DOMICILIO = ("Casa", "Edificio", "Pasillo", "Empresa")

BAF = (
    Field("fecha", "Fecha de ingreso", kind="datetime", required=True, width=125),
    Field("vendedor_id", "Vendedor", kind="select", required=True, width=100, ref="empleados"),
    Field("nombre", "Titular", required=True, width=150),
    Field("documento", "DNI / CUIT", width=100, digits=(7, 8, 11), in_table=False),
    Field("fecha_nacimiento", "Fecha de nacimiento", kind="date", in_table=False),
    Field("email", "Mail", in_table=False),
    Field("telefono", "Teléfono", required=True, width=100, digits=10),
    Field("telefono_alt", "Alternativo", digits=10, in_table=False),
    Field("localidad", "Localidad", required=True, width=110, in_table=False),
    Field("calle", "Calle", required=True, width=130, in_table=False),
    Field("altura", "Altura", required=True, width=60, in_table=False),
    Field("entre_calles", "Entre calles", in_table=False),
    Field("torre_piso_depto", "Torre, piso y depto.", in_table=False),
    Field("tipo_domicilio", "Tipo de domicilio", kind="list", required=True, options=TIPOS_DOMICILIO, in_table=False),
    Field("plan_id", "Plan de internet", kind="select", width=90, ref="planes_baf"),
    Field("cantidad_tv", "Cantidad de TV", kind="list", options=("N/A", "1", "2", "3"), width=50, in_table=False),
    Field("fecha_pactada", "Fecha pactada", kind="date", width=90),
    Field("franja", "Franja pactada", kind="list", options=("AM", "PM"), width=50, in_table=False),
    Field("ot", "Código de OT", width=90),
    Field("sds", "Código de SDS", width=90),
    Field("fecha_instalacion", "Fecha de instalación", kind="date", width=110),
    Field("estado", "Estado", kind="list", options=ESTADOS_BAF, width=90),
    Field("con_form", "Cargado en el formulario", kind="bool"),
    Field("observaciones", "Observaciones", width=150, stretch=True, in_table=False),
)

CATER = (
    Field("fecha", "Fecha y hora", kind="datetime", required=True, width=125),
    Field("nombre", "Nombre o Razón", required=True, width=140),
    Field("numero", "Número", required=True, width=100, digits=10),
    Field("equipo_id", "Equipo", kind="select", required=True, width=190, ref="equipos", suggests="monto"),
    Field("imei", "IMEI", width=130, digits=15),
    Field("monto", "Monto", kind="money", width=90),
    Field("pagos", "Pagos", kind="pagos", ref="cuentas", total="monto", in_table=False),
    Field("vendedor_id", "Vendedor", kind="select", width=100, ref="empleados"),
    Field("sucursal_id", "Sucursal", kind="select", required=True, width=100, ref="sucursales"),
    Field("observaciones", "Observaciones", width=160, stretch=True),
)

# Nuevo > Gasto: plata que sale (se resta en la caja)
GASTOS = (
    Field("fecha", "Fecha y hora", kind="datetime", required=True, width=130),
    Field("detalle", "Detalle", required=True, width=180, stretch=True),
    Field("factura", "Factura", width=100),
    Field("monto", "Monto", kind="money", required=True, width=100),
    Field("cuenta_id", "Cuenta", kind="select", required=True, width=110, ref="cuentas"),
    Field("vendedor_id", "Vendedor", kind="select", width=110, ref="empleados"),
    Field("sucursal_id", "Sucursal", kind="select", required=True, width=110, ref="sucursales"),
    Field("observaciones", "Observaciones", width=160, stretch=True),
)

# Administración
PLANES = (   # planes vigentes: el que se da de baja deja de ofrecerse en las gestiones (Regular, Porta...)
    Field("codigo", "Nombre clave", required=True, width=130),
    Field("descripcion", "Descripción", required=True, width=400, stretch=True),
)

PLANES_BAF = (   # planes de fibra (200MB, 500MB...)
    Field("codigo", "Nombre clave", required=True, width=130),
    Field("descripcion", "Descripción", required=True, width=400, stretch=True),
)

DESCUENTOS = (
    Field("codigo", "Nombre clave", required=True, width=130),
    Field("descripcion", "Descripción", required=True, width=400, stretch=True),
)

SUCURSALES = (
    Field("codigo", "Nombre clave", required=True, width=120),
    Field("entidad", "Entidad", in_table=False),
    Field("nombre", "Nombre", required=True, width=160, stretch=True),
    Field("calle", "Calle", in_table=False),
    Field("numero", "Número", in_table=False),
    Field("piso_depto", "Piso / Depto", in_table=False),
    Field("telefono", "Teléfono", in_table=False),
    Field("ciudad", "Ciudad", kind="choice", width=120),
    Field("cp", "CP", in_table=False),
    Field("provincia", "Provincia", kind="choice", width=120),
    Field("responsable", "Responsable", width=130),
    Field("celular", "Celular", width=110),
)

EMPLEADOS = (
    Field("nombre", "Nombre", required=True, width=200, stretch=True),
    Field("rol", "Rol", kind="choice", width=130),
    Field("celular", "Celular", width=120),
    Field("sucursales", "Sucursales", kind="multi", ref="sucursales", width=240),
)

CUENTAS = (
    Field("codigo", "Nombre clave", required=True, width=130),
    Field("tipo", "Tipo", kind="choice", required=True, width=150),
    Field("descripcion", "Descripción", required=True, width=320, stretch=True),
    Field("saldo_inicial", "Saldo inicial", kind="money", width=130),
)

# Movimientos de stock (Stock > Movimientos). Misma planilla para accesorios y equipos.
TIPOS_MOVIMIENTO = ("INGRESO", "VENTA", "CONCILIACION")   # suman / restan / ajustan (con signo) el stock


def _movimientos(producto_ref, imei=False):
    """`imei`: la venta de un equipo puede llevar el IMEI de la unidad, que se da de baja de los cargados."""
    return (
        Field("fecha", "Fecha y hora", kind="datetime", required=True, width=125),
        Field("tipo", "Tipo", kind="list", required=True, options=TIPOS_MOVIMIENTO, width=100),
        Field("producto_id", "Producto", kind="select", required=True, ref=producto_ref, width=200, stretch=True),
        Field("cantidad", "Cantidad", kind="int", required=True, signed=True, default="1", width=70),
        *((Field("imei", "IMEI (de la venta)", digits=15, in_table=False),) if imei else ()),
        Field("precio", "Precio unitario", kind="money", width=100),
        Field("cliente", "Cliente", default="CONSUMIDOR FINAL", width=120, stretch=True),
        Field("medio", "Medio de cobro", kind="list", options=MEDIOS_COBRO, width=90),
        Field("vendedor_id", "Vendedor", kind="select", ref="empleados", width=100, stretch=True),
        Field("sucursal_id", "Sucursal", kind="select", required=True, ref="sucursales", width=100, stretch=True),
        Field("cupon", "Nº cupón", in_table=False),
        Field("factura", "Factura", in_table=False),
        Field("observaciones", "Observaciones", in_table=False),
    )


MOV_ACCESORIOS = _movimientos("accesorios")
MOV_EQUIPOS = _movimientos("equipos", imei=True)
