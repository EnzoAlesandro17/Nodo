"""Excel del pedido de equipos, con el formato que se usaba en AsistenteCaja: IMEI, MODELO, DESTINO y PEDIDO."""

HEADERS = ["IMEI", "MODELO", "DESTINO ", "PEDIDO"]


def generar(path, destino, pedido, items):
    """`items`: [(imei, modelo)]. Necesita openpyxl (ImportError si no está instalado)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    borde = Border(*(Side(style="thin"),) * 4)
    centrado = Alignment(horizontal="center", vertical="center")
    blanco = PatternFill(fill_type="solid", fgColor="FFFFFFFF")
    wb = Workbook()
    ws = wb.active
    ws.title = "Hoja1"
    for letra, ancho in {"A": 30.71, "B": 34.43, "C": 20.71, "D": 20.71}.items():
        ws.column_dimensions[letra].width = ancho
    ws.row_dimensions[1].height = 29.25
    for col, texto in enumerate(HEADERS, start=1):
        c = ws.cell(1, col, texto)
        c.font, c.alignment, c.border = Font(name="Arial", size=16, bold=True), centrado, borde
    pedido_valor = int(pedido) if str(pedido).strip().isdigit() else pedido
    for fila, (imei, modelo) in enumerate(items, start=2):
        c = ws.cell(fila, 1, str(imei))   # texto, para no perder dígitos por notación científica
        c.font, c.alignment, c.border, c.fill, c.number_format = Font(name="Arial", size=10), centrado, borde, blanco, "@"
        c = ws.cell(fila, 2, modelo)
        c.font, c.border = Font(name="Arial", size=11, color="FF333333"), borde
        c = ws.cell(fila, 3, destino)
        c.font, c.alignment, c.border, c.fill = Font(name="Arial", size=10), centrado, borde, blanco
        c = ws.cell(fila, 4, pedido_valor)
        c.font, c.alignment, c.border = Font(name="Arial", size=10, color="FF000000"), centrado, borde
    ws.auto_filter.ref = f"A1:D{1 + len(items)}"
    wb.save(path)
