"""Inicio: fecha y clima, resumen del día, novedades, agenda (instalaciones de BAF y portaciones), avisos y accesos
directos."""
from datetime import date
from tkinter import ttk

from db import agenda, caja, connection, operaciones, pendientes
from ui import backup_ui, clima, theme
from ui.base import Screen
from ui.formatting import fmt_date, fmt_int, fmt_money
from ui.period_filter import MESES

DIAS_SEMANA = ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")
NOMBRES_TIPO = {"ACCESORIOS": "Accesorios", "EQUIPOS": "Equipos", "CASIM": "CaSIM", "CATER": "CaTER",
                "REGULAR": "Regular", "PORTA": "Porta", "BAF": "BAF"}
DIAS_AGENDA = 14

DIAS_IMEI = 60   # a partir de ahí Claro penaliza (ver ui/imei_dialog.py)


class Inicio(Screen):
    title = "Nodo"
    subtitle = ""
    actions = ()   # sin barra inferior

    def build(self, card):
        card.configure(padding=(22, 14))
        app = self.winfo_toplevel()
        hoy = date.today()
        hoy_iso, mes_iso = hoy.isoformat(), hoy.replace(day=1).isoformat()
        del_dia = caja.movimientos(hoy_iso, hoy_iso)
        del_mes = caja.movimientos(mes_iso, hoy_iso)
        vendido_dia, _, gastos_dia, _ = caja.totales(del_dia)
        _, _, _, neto_mes = caja.totales(del_mes)
        ops_dia = len(operaciones.operaciones(hoy_iso, hoy_iso, solo_vigentes=True))
        sims = connection.get().execute(
            "SELECT COALESCE(sum(stock), 0) FROM equipos WHERE activo = 1 AND marca = 'SIM' AND virtual = 0").fetchone()[0]

        # --- fecha y clima
        cabeza = ttk.Frame(card, style="Inner.TFrame")
        cabeza.pack(fill="x", pady=(0, 6))
        ttk.Label(cabeza, text=f"{DIAS_SEMANA[hoy.weekday()]} {hoy.day} de {MESES[hoy.month - 1].lower()}",
                  style="Card.TLabel", font=theme.FONT_BOLD).pack(side="left")
        lbl_clima = ttk.Label(cabeza, style="Muted.TLabel")
        lbl_clima.pack(side="right")
        clima.pedir(lbl_clima, lambda texto: lbl_clima.config(text=texto))

        # --- números del día
        fila = ttk.Frame(card, style="Inner.TFrame")
        fila.pack(fill="x")
        for col, (rotulo, valor, nota) in enumerate((
                ("Vendido hoy", fmt_money(vendido_dia), f"{ops_dia} operaciones"),
                ("Gastos hoy", fmt_money(gastos_dia), ""),
                ("Caja del mes (neto)", fmt_money(neto_mes), f"ventas menos gastos, desde el {hoy.replace(day=1):%d/%m}"),
                ("SIM en stock", fmt_int(sims), "USIM físicas"))):
            fila.columnconfigure(col, weight=1, uniform="k")
            tarjeta = ttk.Frame(fila, style="Inner.TFrame", padding=(0, 0, 16, 0))
            tarjeta.grid(row=0, column=col, sticky="ew")
            ttk.Label(tarjeta, text=rotulo, style="Muted.TLabel").pack(anchor="w")
            ttk.Label(tarjeta, text=valor, style="Card.TLabel", font=("Segoe UI", 17, "bold")).pack(anchor="w")
            ttk.Label(tarjeta, text=nota, style="Muted.TLabel").pack(anchor="w")

        # --- a la izquierda, las novedades de hoy y lo que hay que revisar; a la derecha, la agenda
        ttk.Separator(card).pack(fill="x", pady=8)
        medio = ttk.Frame(card, style="Inner.TFrame")
        medio.pack(fill="x")
        medio.columnconfigure(0, weight=1, uniform="m")
        medio.columnconfigure(1, weight=1, uniform="m")
        izquierda = ttk.Frame(medio, style="Inner.TFrame", padding=(0, 0, 16, 0))
        izquierda.grid(row=0, column=0, sticky="nsew")
        self._agenda(ttk.Frame(medio, style="Inner.TFrame"), hoy).grid(row=0, column=1, sticky="nsew")

        ttk.Label(izquierda, text="Novedades de hoy", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w")
        nov = agenda.novedades(hoy)
        cargado = "  ·  ".join(f"{NOMBRES_TIPO[t]} {n}" for t, n in nov["operaciones"].items())
        ttk.Label(izquierda, text=("Cargado: " + cargado) if cargado else "Todavía no se cargó nada hoy.",
                  style="Card.TLabel", wraplength=520, justify="left").pack(anchor="w", pady=(4, 0))
        para_hoy = sum(1 for f in agenda.agenda(hoy, 0) if f["fecha"] == hoy.isoformat())
        ttk.Label(izquierda, style="Card.TLabel", text=(
            f"Para hoy: {para_hoy} " + ("instalación o portación" if para_hoy == 1 else "instalaciones o portaciones")
            if para_hoy else "Para hoy no hay instalaciones ni portaciones.")).pack(anchor="w")
        ttk.Label(izquierda, style="Card.TLabel", text=(
            f"Arqueos de hoy: {nov['arqueos']}" if nov["arqueos"] else "Todavía no se hizo el arqueo de hoy."),
            foreground=theme.TEXT if nov["arqueos"] else theme.DANGER).pack(anchor="w")

        ttk.Label(izquierda, text="Para revisar", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w", pady=(8, 0))
        avisos = ttk.Frame(izquierda, style="Inner.TFrame")
        avisos.pack(fill="x", pady=(4, 0))
        por_completar = pendientes.total()
        viejos = connection.get().execute(
            "SELECT count(*) FROM imeis WHERE activo = 1 AND julianday('now', 'localtime') - julianday(fecha_ingreso) >= ?",
            (DIAS_IMEI,)).fetchone()[0]
        texto_copia, avisar = backup_ui.texto_ultima_copia()
        lineas = [
            (f"{fmt_int(por_completar)} registros por completar (ID de gestión, números mal cargados, empleados sin sucursal...)"
             if por_completar else "No hay registros por completar.", bool(por_completar), "Ver", "pendientes"),
            (f"{viejos} equipo{'' if viejos == 1 else 's'} con {DIAS_IMEI} días o más en stock (Claro penaliza)"
             if viejos else f"Ningún equipo con {DIAS_IMEI} días o más en stock.", bool(viejos), "Ver", "equipos"),
            (texto_copia, avisar, "Hacer copia ahora", "copia"),
        ]
        for n, (texto, alerta, boton, accion) in enumerate(lineas):
            avisos.columnconfigure(0, weight=1)
            ttk.Label(avisos, text=("● " if alerta else "✓ ") + texto, style="Card.TLabel", wraplength=420,
                      foreground=theme.DANGER if alerta else theme.OK).grid(row=n, column=0, sticky="w", pady=1)
            ttk.Button(avisos, text=boton, command=lambda a=accion: self._accion(a)).grid(row=n, column=1, padx=(12, 0), pady=1)

        # --- accesos directos
        ttk.Separator(card).pack(fill="x", pady=8)
        ttk.Label(card, text="Accesos directos", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w")
        grilla = ttk.Frame(card, style="Inner.TFrame")
        grilla.pack(fill="x", pady=(6, 0))
        columnas = 6
        for n, (rotulo, tecla, pantalla) in enumerate(getattr(app, "accesos", [])):
            grilla.columnconfigure(n % columnas, weight=1, uniform="a")
            texto = f"{rotulo}   [{tecla}]" if tecla else rotulo
            ttk.Button(grilla, text=texto, command=lambda p=pantalla: app.show(p)).grid(
                row=n // columnas, column=n % columnas, sticky="ew", padx=(0, 8), pady=(0, 6))

    def _agenda(self, marco, hoy):
        """Instalaciones de BAF y portaciones de los próximos días (y las BAF atrasadas). Doble clic abre la gestión."""
        ttk.Label(marco, text=f"Próximas instalaciones y portaciones ({DIAS_AGENDA} días)", style="Card.TLabel",
                  font=theme.FONT_BOLD).pack(anchor="w")
        columnas = (("fecha", "Fecha", 90), ("tipo", "Tipo", 60), ("cliente", "Cliente", 170), ("detalle", "Detalle", 150))
        tree = ttk.Treeview(marco, columns=[c[0] for c in columnas], show="headings", height=5, selectmode="browse")
        for clave, texto, ancho in columnas:
            tree.heading(clave, text=texto, anchor="w")
            tree.column(clave, width=ancho, minwidth=50, anchor="w", stretch=clave == "detalle")
        tree.pack(fill="both", expand=True, pady=(4, 0))
        tree.tag_configure("hoy", background=theme.FILA_PENDIENTE)
        tree.tag_configure("atrasada", foreground=theme.DANGER)
        filas = agenda.agenda(hoy, DIAS_AGENDA)
        self._filas_agenda = {}
        for f in filas:
            iid = f"{f['origen']}:{f['id']}"
            self._filas_agenda[iid] = f
            etiqueta = "atrasada" if f["atrasada"] else "hoy" if f["fecha"] == hoy.isoformat() else ""
            tree.insert("", "end", iid=iid, tags=(etiqueta,) if etiqueta else (), values=(
                fmt_date(f["fecha"]) + (" (atrasada)" if f["atrasada"] else ""),
                "Porta" if f["tipo"] == "PORTA" else "BAF", f["cliente"], f["detalle"]))
        if not filas:
            tree.insert("", "end", values=("", "", "Nada agendado.", ""))
        tree.bind("<Double-1>", lambda e: self._abrir(tree.identify_row(e.y)))
        return marco

    def _abrir(self, iid):
        """Abre la pantalla de la gestión elegida en la agenda, con su formulario de edición."""
        fila = self._filas_agenda.get(iid)
        if not fila:
            return
        from ui.screens import gestiones
        app = self.winfo_toplevel()
        app.show(gestiones.BAF if fila["origen"] == "baf" else gestiones.Porta)
        pantalla = app.current
        if str(fila["id"]) in pantalla.tree.get_children():
            pantalla.tree.selection_set(str(fila["id"]))
            pantalla.tree.see(str(fila["id"]))
            pantalla.edit()

    def _accion(self, accion):
        app = self.winfo_toplevel()
        if accion == "copia":
            if backup_ui.hacer_copia(app):
                app.show(Inicio)
            return
        from ui.screens import pendientes as pantalla_pendientes, stock
        app.show(pantalla_pendientes.Pendientes if accion == "pendientes" else stock.StockEquipos)
