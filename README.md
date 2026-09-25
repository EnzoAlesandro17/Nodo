# Nodo

Gestión de una sucursal de telefonía: stock de accesorios y equipos, ventas, gestiones de Claro (CaSIM, CaTER,
Regular, Porta, BAF), gastos, caja y arqueo. Es una app de escritorio para Windows (Python + Tkinter) que busca
reemplazar la planilla de Excel de la caja (CAJA3ROSARIO).

## Requisitos

- Windows y Python 3.10 o más nuevo (python.org, con "Add to PATH"). Se usa con 3.14.
- La única dependencia es `openpyxl`, que se usa para leer y escribir Excel.

## Instalar y abrir

```bat
crear_entorno.bat    :: una vez por PC: arma .venv e instala requirements.txt
iniciar_nodo.bat     :: abre la app (main.pyw con el pythonw de .venv)
```

La base se crea sola en `data/nodo.db` la primera vez que se abre la app. Está fuera de git (`.gitignore`) porque
tiene datos de clientes.

## Tests

```bat
.venv\Scripts\python -m unittest discover -s tests
```

Los tests nunca tocan `data/nodo.db`. Cada uno trabaja sobre una base temporal (vacía o una copia de la real) que
se indica con la variable de entorno `NODO_DB`. Algunos revisan la base real (el stock es igual a la suma de los
movimientos, no hay referencias rotas, los arqueos están encadenados): si no hay base, esos se saltean. Hay que
correrlos antes de cada cambio.

## Estructura

```
app.py, main.pyw     ventana principal, menú y atajos (F1 a F8)
models.py            campos de cada tabla (Field): los usan la base, los formularios, las tablas y los CSV
db/                  acceso a datos, sin nada de interfaz
  connection.py      esquema (SCHEMA), migraciones numeradas (MIGRACIONES) y la conexión
  repo.py            Repo genérico: listar, alta, edición y baja lógica
  gestiones.py       CaSIM, CaTER, Regular, Porta, BAF, gastos y tareas
  movimientos.py     movimientos de stock (ingreso, venta, conciliación)
  ventas.py          venta de accesorios con varios productos y pagos combinados
  caja.py            la Caja: se arma leyendo las demás tablas, no guarda nada
  importer.py        CSV del menú Data
  formulario_baf.py  link precargado del formulario de Google de las BAF (se revisa y se envía a mano)
ui/                  interfaz Tkinter, sin SQL
  screens/           una pantalla por archivo
  table_base.py, gestion_base.py, form_dialog.py   tabla + formulario genéricos
tests/               unittest
assets/              ícono de la ventana
```

## Reglas del proyecto

- **Una sola base, un solo archivo:** SQLite con `journal_mode = delete`, sin `-wal` ni `-shm`. No se guardan copias
  dentro de `data/`. Para respaldarla: Data > Copia de seguridad, que usa la API de copia de SQLite y funciona con la
  app abierta.
- **El esquema se cambia con una migración nueva:** se agrega una función `_mNN_...` al final de `MIGRACIONES` en
  `db/connection.py` y se actualiza también `SCHEMA`, para que una base nueva nazca igual. La versión queda en
  `PRAGMA user_version` y las migraciones se aplican solas al abrir la app. La app no abre una base de una versión
  más nueva que ella. Un test compara una base migrada con una nueva.
- **Claves foráneas activadas** en cada conexión.
- **Las bajas son lógicas** (`activo = 0`). Los arqueos no se editan ni se borran, para evitar cambios de mala fe.
- **El stock es la suma de los movimientos:** INGRESO suma, VENTA resta y CONCILIACION ajusta, con signo. Las
  gestiones que entregan un producto (la SIM de CaSIM, Regular y Porta; el equipo de CaTER) generan su movimiento en
  la misma transacción, y editarlas o darlas de baja lo actualiza o lo revierte. Los productos virtuales (E-SIM,
  el equipo PENDIENTE) no llevan stock.
- **Capas:** `db/` no importa nada de `ui/`, y `ui/` no escribe SQL. La excepción es `ui/formatting.py`, que son
  funciones puras. Los tests lo verifican.
- **Importes:** se guardan como REAL y se muestran con coma decimal (es-AR). Se redondea a 2 decimales solo lo que se
  muestra, se compara o se guarda; los pasos intermedios no se redondean.
- **Interfaz:** todas las tablas con fecha usan el mismo renglón de filtros: Buscar, el filtro de la tabla y el
  período (`ui/period_filter.py`). Los desplegables sugieren mientras se escribe (`ui/autocomplete.py`); las listas
  cerradas solo aceptan sus opciones.
- El código, los comentarios y los textos de la interfaz están en español.

## El negocio, en lo que importa al código

- **Gestiones:** CaSIM (venta de un chip, $500 en efectivo), CaTER (venta de un equipo de Claro), Regular (línea
  nueva), Porta (portabilidad) y BAF (fibra óptica). Regular, Porta y BAF no cobran: aparecen en la Caja con monto 0.
- **Cuentas de cobro** (`models.CUENTAS_DE_COBRO`): la terminal GETNET y sus subcuentas (GETNET VISA, GETNET QR...),
  y CLARO con las suyas (FINANCIADO, QR, TC-CTI). Se cobra siempre con una subcuenta. Las cuentas de tipo CLARO
  (`models.TIPO_FUERA_DE_CAJA`) registran cómo se cobró algo cuya plata va a Claro: la Caja las muestra pero no las
  suma, y aceptan pagos sin monto. Los bancos son cuentas sueltas.
- **Intereses:** los calcula la terminal, no Nodo. En la venta de accesorios se carga lo cobrado aparte y la Caja lo
  muestra como INTERESES, fuera de las ventas.
- **Planes** (Regular y Porta usan los mismos): 2GB = Control Limítrofes 20, 4GB = Control América 68, 7GB = Control
  América 69, 10GB = Control Europa 5, 30GB = Control Asia 3, 50GB = Control Mundo; PREPAGO. Los descuentos son las
  promos con su código de Claro. Hay que actualizarlos cuando cambia la guía del vendedor.
- **IMEI:** desde los 60 días en stock, Claro empieza a penalizar: por eso se marcan en rojo. El precio que aparece
  en las listas de Claro es lo que Claro le cobra al agente, no el precio de venta: no se guarda.
- **Códigos de sucursal:** una letra por tipo y un número correlativo (A administración, L local, C callcenter,
  B BAF, I instaladora...): L002 = 3ROSARIO.
- **Arqueo:** caja fuerte + caja chica - saldo del sistema. Cada monto se puede escribir como suma (+100.000+50.000).
  La variación de un arqueo es su resultado menos el del anterior.

## Datos entre sucursales

Cada sucursal tiene su propia base, y los archivos SQLite no se comparten por red. Lo que tiene que ser igual en
todas (áreas, sucursales, empleados, cuentas, planes, precios sugeridos) se reparte con los CSV del menú Data:

- Separador `;` y coma decimal. Al importar también acepta `,` o tabulador, y UTF-8 o Windows-1252.
- Cada registro se busca por su clave: el código, el nombre clave o, en empleados, el nombre. El que existe se
  actualiza, el nuevo se agrega y una celda vacía deja el valor como está. El stock nunca se toca.
- Hay vista previa antes de aplicar, y todo se aplica en una sola transacción.
- Orden de carga en una base nueva: Áreas, después Sucursales y después el resto. Los empleados traen sus
  sucursales por nombre clave.
