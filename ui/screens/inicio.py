"""Inicio: resumen del día, avisos y accesos directos."""
from datetime import date
from tkinter import ttk

from db import caja, connection, operaciones, pendientes
from ui import backup_ui, theme
from ui.base import Screen
from ui.formatting import fmt_int, fmt_money

DIAS_IMEI = 60   # a partir de ahí Claro penaliza (ver ui/imei_dialog.py)


class Inicio(Screen):
    title = "Nodo"
    subtitle = ""
    actions = ()   # sin barra inferior

    def build(self, card):
        card.configure(padding=22)
        app = self.winfo_toplevel()
        hoy = date.today()
        hoy_iso, mes_iso = hoy.isoformat(), hoy.replace(day=1).isoformat()
        del_dia = caja.movimientos(hoy_iso, hoy_iso)
        del_mes = caja.movimientos(mes_iso, hoy_iso)
        vendido_dia, _, gastos_dia, _ = caja.totales(del_dia)
        _, _, _, neto_mes = caja.totales(del_mes)
        ops_dia = len(operaciones.operaciones(hoy_iso, hoy_iso, solo_vigentes=True))
        sims = connection.get().execute(
            "SELECT COALESCE(sum(stock), 0) FROM accesorios WHERE activo = 1 AND categoria = 'SIMS' AND virtual = 0").fetchone()[0]

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

        # --- avisos
        ttk.Separator(card).pack(fill="x", pady=12)
        ttk.Label(card, text="Para revisar", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w")
        avisos = ttk.Frame(card, style="Inner.TFrame")
        avisos.pack(fill="x", pady=(6, 0))
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
            ttk.Label(avisos, text=("● " if alerta else "✓ ") + texto, style="Card.TLabel",
                      foreground=theme.DANGER if alerta else theme.OK).grid(row=n, column=0, sticky="w", pady=2)
            ttk.Button(avisos, text=boton, command=lambda a=accion: self._accion(a)).grid(row=n, column=1, padx=(12, 0), pady=2)

        # --- accesos directos
        ttk.Separator(card).pack(fill="x", pady=12)
        ttk.Label(card, text="Accesos directos", style="Card.TLabel", font=theme.FONT_BOLD).pack(anchor="w")
        grilla = ttk.Frame(card, style="Inner.TFrame")
        grilla.pack(fill="x", pady=(8, 0))
        columnas = 4
        for n, (rotulo, tecla, pantalla) in enumerate(getattr(app, "accesos", [])):
            grilla.columnconfigure(n % columnas, weight=1, uniform="a")
            texto = f"{rotulo}   [{tecla}]" if tecla else rotulo
            ttk.Button(grilla, text=texto, command=lambda p=pantalla: app.show(p)).grid(
                row=n // columnas, column=n % columnas, sticky="ew", padx=(0, 8), pady=(0, 6))

    def _accion(self, accion):
        app = self.winfo_toplevel()
        if accion == "copia":
            if backup_ui.hacer_copia(app):
                app.show(Inicio)
            return
        from ui.screens import pendientes as pantalla_pendientes, stock
        app.show(pantalla_pendientes.Pendientes if accion == "pendientes" else stock.StockEquipos)
