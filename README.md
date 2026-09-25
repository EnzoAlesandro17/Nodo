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

La base se crea sola en `data/nodo.db` la primera vez que se abre la app. Está fuera de git (`.gitignore`): tiene
datos de clientes y cada sucursal tiene la suya.

## Tests

```bat
.venv\Scripts\python -m unittest discover -s tests
```

Los tests nunca tocan `data/nodo.db`. Cada uno trabaja sobre una base temporal (vacía o una copia de la real) que
se indica con la variable de entorno `NODO_DB`. Algunos revisan la base real, por ejemplo que el stock sea igual a
la suma de los movimientos o que no haya referencias rotas: si no hay base, esos se saltean.

## Estructura

```
app.py, main.pyw     ventana principal, menú y atajos (F1 a F8)
models.py            campos de cada tabla (Field): los usan la base, los formularios, las tablas y los CSV
db/                  acceso a datos, sin nada de interfaz
  connection.py      esquema (SCHEMA), migraciones numeradas (MIGRACIONES) y la conexión
  repo.py            Repo genérico: listar, alta, edición y baja lógica
  gestiones.py       CaSIM, CaTER, Regular, Porta, BAF, gastos y tareas
  movimientos.py     movimientos de stock (ingreso, venta, conciliación)
  caja.py            la Caja: se arma leyendo las demás tablas, no guarda nada
  ...
ui/                  interfaz Tkinter, sin SQL
  screens/           una pantalla por archivo
  table_base.py, gestion_base.py, form_dialog.py   tabla + formulario genéricos
tests/               unittest
assets/              ícono de la ventana
HOJA_DE_RUTA.txt     registro detallado de decisiones, cargas de datos y pendientes
```

## Reglas del proyecto

- **Una sola base, un solo archivo:** SQLite con `journal_mode = delete`, sin `-wal` ni `-shm`. Para respaldarla
  alcanza con copiar el archivo con la app cerrada, o usar Data > Copia de seguridad, que funciona con la app abierta.
- **El esquema se cambia con una migración nueva:** se agrega una función `_mNN_...` al final de `MIGRACIONES` en
  `db/connection.py` y se actualiza también `SCHEMA`, para que una base nueva nazca igual. La versión queda en
  `PRAGMA user_version` y las migraciones se aplican solas al abrir la app. Un test compara una base migrada con una
  nueva.
- **Claves foráneas activadas** en cada conexión.
- **Las bajas son lógicas** (`activo = 0`): no se borran registros desde la app. Los arqueos no se editan ni se borran.
- **El stock es la suma de los movimientos:** cada venta, ingreso o conciliación suma o resta, y las gestiones que
  entregan un producto generan su propio movimiento.
- **Capas:** `db/` no importa nada de `ui/`, y `ui/` no escribe SQL. Los tests lo verifican.
- **Importes:** se guardan como REAL y se muestran con coma decimal (es-AR). Solo se redondea lo que se muestra o
  se guarda.
- El código, los comentarios y los textos de la interfaz están en español.

## Datos entre sucursales

Cada sucursal tiene su propia base, y los archivos SQLite no se comparten por red. Lo que tiene que ser igual en
todas (áreas, sucursales, empleados, cuentas, planes, precios sugeridos) se reparte con los CSV del menú Data. Los
CSV usan `;` como separador y coma decimal, y la importación muestra una vista previa antes de aplicar.
