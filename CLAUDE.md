# Notas para Claude

Leé README.md (reglas del proyecto) y RODO.txt (estado y pendientes). HOJA_DE_RUTA.txt tiene el detalle de cada
decisión y de cada carga de datos: sumá ahí una entrada fechada cuando cambies algo de fondo.

## Comandos

- Tests: `.venv\Scripts\python -m unittest discover -s tests` (no hay pytest).
- Abrir la app sin que dependa de la sesión de Claude: `explorer.exe iniciar_nodo.bat`. Si se lanza desde la
  terminal de Claude, se cierra cuando Claude se reinicia o se actualiza.
- Cerrar la app: `CloseMainWindow()` sobre el proceso `pythonw` con título "Nodo". Hay dos procesos por el
  lanzador del venv: eso es normal.

## Al tocar datos de la base real (data/nodo.db)

- Siempre antes: una copia con `sqlite3.backup` (nunca dentro de data/).
- Cargar a través de los repos (`db.gestiones`, `db.movimientos`, `db.ventas`) y no con INSERT directos, para que se
  generen los movimientos, el stock y los pagos.
- Primero una pasada de prueba que muestre qué va a hacer; después aplicar. Al final, verificar: stock igual a la
  suma de los movimientos, `PRAGMA foreign_key_check` y los tests.
- La base de casa y la del trabajo son distintas (ver RODO.txt): los cambios de datos que se hagan en una no llegan a
  la otra. Los cambios de esquema sí llegan, por las migraciones.

## Convenciones

- Todo en español: código, comentarios, mensajes, commits. Docstrings cortos que dicen el porqué.
- Cambios de esquema: una migración `_mNN_` nueva, más `SCHEMA` y un test si hay datos que transformar. Tiene que
  poder repetirse sin daño.
- `db/` no importa `ui/`, y `ui/` no escribe SQL: hay tests que lo verifican.
- Datos de negocio: las cuentas de tipo CLARO no suman en la Caja (`models.TIPO_FUERA_DE_CAJA`). Las subcuentas
  llevan el código de su padre adelante (GETNET VISA). Se cobra siempre con una subcuenta, nunca con la padre.
- En la terminal Bash de esta PC, un heredoc largo con comillas mezcladas puede fallar: para ediciones grandes,
  escribí un script .py y corrélo.
