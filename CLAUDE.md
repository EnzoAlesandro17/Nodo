# Notas para Claude

Leé README.md (reglas del proyecto y del negocio) y RODO.txt (estado y pendientes, escrito para Enzo: lenguaje
simple, solo lo esencial). No hay otro registro: cuando cambies algo de fondo, actualizá el que corresponda y no
agregues historia de cargas de datos. El repo de GitHub puede ser público: nunca escribas en el repo nombres de
clientes, montos de operaciones ni datos de la base.

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
- Hay una sola base buena (la del trabajo; ver RODO.txt). Los cambios de esquema llegan a cualquier base por las
  migraciones; los cambios de datos, no.

## Cargar desde la planilla CAJA3ROSARIOaamm.xlsx

- Hoja CAJA (desde la fila 4): FECHA, DETALLE ("Apellido 341..."), FAC., INGRESO, SALIDA, Cant, OPERACIÓN,
  TIPO/MODELO, DEST, MODO, Nº, Movim. (vendedor), OBSERVACIONES.
  * CaSIM: OPERACIÓN propio + TIPO/MODELO sim-car + INGRESO 500. Cant 0 u observación E-SIM -> E-SIM (7001374, sin
    stock); si no, la USIM 7001335. No se cobran: sin monto ni cuenta.
  * Regular r2g..r50g y Porta p2g..p50g -> plan 2GB..50GB, la USIM. En Porta, "PORTADA" no se carga como
    observación; "SE PORTA EL dd/m" también va a fecha_portacion.
  * cater: equipo PENDIENTE (virtual). Las observaciones pasan a pagos: "tc-cti $X" -> CLARO TC-CTI por X;
    financiado -> CLARO FINANCIADO y qr -> CLARO QR, sin monto. El Monto es la suma de los pagos.
  * gasto/varios "REPOS" -> gasto VARIOS, cuenta EFE, sin vendedor. No se cargan: ORGA, transfer, Transfer QR en 0.
  * BAF con observación INSTALADA -> la BAF existente pasa a Instalada con esa fecha.
- Hoja CajaAcc: las ventas "Consumidor final" -> movimiento VENTA de accesorios: código de barras (sin distinguir
  mayúsculas), Cant, INGRESO (precio unitario), MODO -> GETNET + la tarjeta (efe -> EFE), Nº = cupón.
- La caja no tiene hora: fecha a las 00:00. Antes de cargar, comparar por (fecha, número) con lo que ya está: la
  planilla corrige números de días anteriores.

## Convenciones

- Todo en español: código, comentarios, mensajes, commits. Docstrings cortos que dicen el porqué.
- Cambios de esquema: una migración `_mNN_` nueva, más `SCHEMA` y un test si hay datos que transformar. Tiene que
  poder repetirse sin daño.
- `db/` no importa `ui/`, y `ui/` no escribe SQL: hay tests que lo verifican.
- Anchos de columna de Áreas, Sucursales y Empleados en múltiplos de `models.COL` (40 px); la última columna absorbe
  el espacio sobrante.
- En la terminal Bash de esta PC, un heredoc largo con comillas mezcladas puede fallar: para ediciones grandes,
  escribí un script .py y corrélo.
