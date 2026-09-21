"""Pantalla genérica de stock: productos con alta / edición / baja (CodigoScreen)."""
from ui.codigo_base import CodigoScreen


class StockScreen(CodigoScreen):
    """Stock de productos. La carga masiva por CSV está en la sección Data."""
    noun, noun_plural = "producto", "productos"
    form_new, form_edit = "Nuevo producto", "Editar producto"

    def _display(self, field, row):
        if field.key == "stock" and row.get("virtual"):
            return "—"   # producto virtual: no maneja stock
        return super()._display(field, row)
