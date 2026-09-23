"""Definición de los campos de cada tabla. La usan tanto la base de datos como la UI.

`key` coincide con el nombre de la columna en SQLite.
`kind`: text | choice (texto con sugerencias de lo ya cargado) | email | money | int | bool | select | datetime | multi | list
(email = texto en minúsculas, con formato de dirección de mail;
 list = lista cerrada de textos fijos (`options`);
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
    section: str = ""       # formulario: título que agrupa este campo con los siguientes de la misma sección


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
    Field("virtual", "Virtual (sin stock)", kind="bool", disables="stock"),   # 1 = la E-SIM
)

MEDIOS_COBRO = ("EFE", "VISA", "MASTER", "MAESTRO", "AMEX", "NARANJA", "CONSUMAX", "QR")   # EFE = efectivo

# Gestiones (menú Nuevo > Gestiones). Cada una es una tabla propia con este formato.
CASIM = (
    Field("fecha", "Fecha y hora", kind="datetime", required=True, width=130),
    Field("nombre", "Nombre o Razón", required=True, width=140),
    Field("numero", "Número", required=True, width=100, digits=10),
    Field("sim_id", "Tipo de SIM", kind="select", required=True, width=160, ref="equipos"),
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
        Field("sim_id", "Tipo de SIM", kind="select", required=True, width=140, ref="equipos", in_table=False),
        Field("sucursal_id", "Sucursal", kind="select", required=True, width=100, ref="sucursales", in_table=False),
        Field("observaciones", "Observaciones", width=140, stretch=True),
    )


# Regular y Porta: obligatorios solo Fecha y hora, Nombre, el número que identifica la línea (Nuevo número / Número
# a portar), Plan, Vendedor, Sucursal y Tipo de SIM; el resto se completa después, editando. En la tabla solo se ven
# Fecha y hora, Nombre, ese número, Plan, Vendedor y Observaciones, con el ancho de Nombre (el doble para Observaciones).
_ANCHO_LINEA = 140   # el de "Nombre o Razón"


def _ajustar_linea(fields, numero_key, ocultos):
    anchos = {"fecha": _ANCHO_LINEA, numero_key: _ANCHO_LINEA, "plan_id": _ANCHO_LINEA, "vendedor_id": _ANCHO_LINEA,
             "observaciones": _ANCHO_LINEA * 2}

    def ajustar(f):
        if f.key == "vendedor_id":
            f = replace(f, required=True)
        if f.key in ocultos:
            f = replace(f, required=False, in_table=False)
        if f.key in anchos:
            f = replace(f, width=anchos[f.key])
        return f

    return tuple(ajustar(f) for f in fields)


REGULAR = _ajustar_linea(_linea(("telefono", "Teléfono de contacto", False), ("numero", "Nuevo número", True)),
                         "numero", ocultos=("telefono", "documento", "descuento_id", "id_gestion"))
COMPANIAS = ("PERSONAL", "MOVISTAR", "IMOWI")   # sugeridas: se puede escribir otra

PORTA = _ajustar_linea(_linea(
    ("numero_portar", "Número a portar", True), ("nim", "NIM temporal", False),
    tras_a=(Field("compania_donante", "Compañía donante", kind="choice", options=COMPANIAS, width=110),
            Field("tipo_negocio", "Tipo de negocio actual", kind="list", options=("PREPAGO", "POSPAGO"), width=100)),
    tras_b=(Field("pin", "PIN de portabilidad", width=90),
            Field("fecha_portacion", "Fecha de portación", kind="date", width=110, in_table=False))),
    "numero_portar", ocultos=("documento", "compania_donante", "tipo_negocio", "descuento_id", "nim", "pin", "id_gestion"))

# BAF (banda ancha fija = fibra óptica): venta e instalación, del titular al estado de la instalación. El
# formulario se agrupa en tres secciones (gestión, titular, servicio); la tabla (ver BAF.columns en
# ui/screens/gestiones.py) muestra solo fecha, nombre, plan, estado, fecha pactada y fecha de instalación.
ESTADOS_BAF = ("Deuda", "HP", "Falta pactar", "Pactada", "Cancelada", "Instalada")
TIPOS_DOMICILIO = ("Casa", "Edificio", "Pasillo", "Empresa")

SECCION_GESTION = "Datos de la gestión"
SECCION_TITULAR = "Datos del titular"
SECCION_SERVICIO = "Datos del servicio"

BAF = (
    Field("fecha", "Fecha de ingreso", kind="datetime", required=True, width=125, section=SECCION_GESTION),
    Field("vendedor_id", "Vendedor", kind="select", required=True, width=100, ref="empleados", in_table=False,
          section=SECCION_GESTION),
    Field("estado", "Estado", kind="list", options=ESTADOS_BAF, width=90, section=SECCION_GESTION),
    Field("fecha_pactada", "Fecha pactada", kind="date", width=90, section=SECCION_GESTION),
    Field("franja", "Franja pactada", kind="list", options=("AM", "PM"), width=50, in_table=False,
          section=SECCION_GESTION),
    Field("fecha_instalacion", "Fecha de instalación", kind="date", width=110, section=SECCION_GESTION),
    Field("ot", "Código de OT", width=90, in_table=False, section=SECCION_GESTION),
    Field("sds", "Código de SDS", width=90, in_table=False, section=SECCION_GESTION),
    Field("con_form", "Cargado en el formulario", kind="bool", section=SECCION_GESTION),
    Field("observaciones", "Observaciones", width=150, stretch=True, in_table=False, section=SECCION_GESTION),

    Field("nombre", "Titular", required=True, width=150, section=SECCION_TITULAR),
    Field("documento", "DNI / CUIT", width=100, digits=(7, 8, 11), in_table=False, section=SECCION_TITULAR),
    Field("fecha_nacimiento", "Fecha de nacimiento", kind="date", in_table=False, section=SECCION_TITULAR),
    Field("email", "Mail", in_table=False, section=SECCION_TITULAR),
    Field("telefono", "Teléfono", required=True, width=100, digits=10, in_table=False, section=SECCION_TITULAR),
    Field("telefono_alt", "Alternativo", digits=10, in_table=False, section=SECCION_TITULAR),

    Field("localidad", "Localidad", required=True, width=110, in_table=False, section=SECCION_SERVICIO),
    Field("calle", "Calle", required=True, width=130, in_table=False, section=SECCION_SERVICIO),
    Field("altura", "Altura", required=True, width=60, in_table=False, section=SECCION_SERVICIO),
    Field("entre_calles", "Entre calles", in_table=False, section=SECCION_SERVICIO),
    Field("torre_piso_depto", "Torre, piso y depto.", in_table=False, section=SECCION_SERVICIO),
    Field("tipo_domicilio", "Tipo de domicilio", kind="list", required=True, options=TIPOS_DOMICILIO, in_table=False,
          section=SECCION_SERVICIO),
    Field("plan_id", "Plan de internet", kind="select", width=90, ref="planes_baf", section=SECCION_SERVICIO),
    Field("cantidad_tv", "Cantidad de TV", kind="list", options=("N/A", "1", "2", "3"), width=50, in_table=False,
          section=SECCION_SERVICIO),
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
RUBROS_GASTO = ("ALQUILER", "AUTOMOTOR", "BANCARIOS", "COMISION", "FLETE", "SERVICIOS", "LIBRERÍA", "LIMPIEZA",
                "PUBLICIDAD", "SUELDOS", "VARIOS", "VIATICOS")   # los de la hoja Gastos de la planilla de caja
GASTOS = (
    Field("fecha", "Fecha y hora", kind="datetime", required=True, width=130),
    Field("rubro", "Rubro", kind="list", options=RUBROS_GASTO, required=True, default="VARIOS", width=100),
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

# Días que el local no abre (feriados, balance...): los carga quien mantiene los datos, año a año.
# Estadísticas los resta de la proyección del mes en curso.
# Administración > Tareas (traídas de MyTools): pendientes del local, abiertas o cerradas
ESTADOS_TAREA = ("Abierta", "Cerrada")
TAREAS = (
    Field("fecha", "Creada", kind="datetime", required=True, width=125),
    Field("titulo", "Tarea", required=True, width=300, stretch=True),
    Field("fecha_limite", "Fecha límite", kind="date", width=100),
    Field("prioritaria", "Prioritaria", kind="bool"),
    Field("estado", "Estado", kind="list", options=ESTADOS_TAREA, required=True, default="Abierta", width=80),
    Field("comentarios", "Comentarios", width=200, in_table=False),
)

CIERRES = (
    Field("fecha", "Fecha", kind="date", required=True, width=110),
    Field("motivo", "Motivo", width=250, stretch=True),
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

EMPLEADOS = (   # el orden es el de las columnas de la tabla y del formulario
    Field("nombre", "Nombre", required=True, width=150),
    Field("rol", "Cargo", kind="choice", width=130),
    Field("sucursales", "Sucursales", kind="multi", ref="sucursales", width=240, stretch=True),
    Field("celular", "Teléfono", width=120),
    Field("email", "Mail", kind="email", width=210),
    Field("fecha_nacimiento", "Fecha de nacimiento", kind="date", width=140),
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
