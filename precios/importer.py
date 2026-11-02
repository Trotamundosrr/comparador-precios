import csv
import io
from decimal import Decimal, InvalidOperation

from openpyxl import Workbook, load_workbook

from .models import Category
from .services import upsert_store_product
from .texto import normalize

COLUMNS = ["nombre", "marca", "presentacion", "categoria", "precio", "codigo_barras", "disponible"]

# normalize() quita tildes y convierte _ en espacio
ALIASES = {
    "nombre": "nombre",
    "marca": "marca",
    "presentacion": "presentacion",
    "categoria": "categoria",
    "precio": "precio",
    "codigo barras": "codigo_barras",
    "codigo de barras": "codigo_barras",
    "disponible": "disponible",
}


def header_key(value):
    return ALIASES.get(normalize(str(value or "")))


def build_template():
    book = Workbook()
    sheet = book.active
    sheet.title = "productos"
    sheet.append(COLUMNS)
    sheet.append(["Leche entera", "PIL", "900 ml", "lacteos", 10.5, "", "si"])
    buffer = io.BytesIO()
    book.save(buffer)
    buffer.seek(0)
    return buffer


def read_table(uploaded):
    name = (uploaded.name or "").lower()
    if name.endswith(".csv"):
        text = uploaded.read().decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        raw_rows = list(reader)
    elif name.endswith(".xlsx"):
        book = load_workbook(uploaded, data_only=True)
        raw_rows = [list(row) for row in book.active.iter_rows(values_only=True)]
    else:
        raise ValueError("Solo se acepta .xlsx o .csv.")

    if not raw_rows:
        raise ValueError("El archivo está vacío.")

    columns = [header_key(cell) for cell in raw_rows[0]]
    if "nombre" not in columns or "precio" not in columns:
        raise ValueError("Faltan las columnas nombre y precio. Usa la plantilla.")

    parsed = []
    for offset, raw in enumerate(raw_rows[1:], start=2):
        row = {}
        for index, key in enumerate(columns):
            if key is None:
                continue
            value = raw[index] if index < len(raw) else ""
            row[key] = "" if value is None else value
        if any(str(value).strip() for value in row.values()):
            parsed.append((offset, row))
    return parsed


def parse_price(value):
    if isinstance(value, float):
        value = round(value, 2)
    text = str(value).strip().replace(",", ".")
    amount = Decimal(text).quantize(Decimal("0.01"))
    if amount <= 0:
        raise InvalidOperation
    return amount


def parse_barcode(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_available(value):
    text = normalize(str(value or "si"))
    if text in ("", "si", "1", "true", "yes"):
        return True
    if text in ("no", "0", "false"):
        return False
    raise ValueError


def find_category(text, categories):
    key = normalize(text)
    for category in categories:
        if normalize(category.slug) == key or normalize(category.name) == key:
            return category
    return None


def import_products(store, rows):
    categories = list(Category.objects.all())
    created = updated = 0
    errors = []

    for number, row in rows:
        problems = {}
        name = str(row.get("nombre") or "").strip()
        if not name:
            problems["nombre"] = "El nombre es obligatorio."

        try:
            amount = parse_price(row.get("precio"))
        except (InvalidOperation, TypeError, ValueError):
            amount = None
            problems["precio"] = "Precio inválido. Usa un número mayor que 0."

        barcode = parse_barcode(row.get("codigo_barras"))
        if barcode and (not barcode.isdigit() or not 8 <= len(barcode) <= 14):
            problems["codigo_barras"] = "Debe tener entre 8 y 14 dígitos."

        category = None
        category_text = str(row.get("categoria") or "").strip()
        if category_text:
            category = find_category(category_text, categories)
            if category is None:
                problems["categoria"] = "Esa categoría no existe."

        try:
            available = parse_available(row.get("disponible"))
        except ValueError:
            available = True
            problems["disponible"] = "Usa si o no."

        if problems:
            errors.append({"fila": number, "errores": problems})
            continue

        _, was_created = upsert_store_product(
            store,
            amount=amount,
            name=name,
            brand=str(row.get("marca") or "").strip(),
            unit=str(row.get("presentacion") or "").strip(),
            category=category,
            barcode=barcode,
            available=available,
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {
        "filas": len(rows),
        "creados": created,
        "actualizados": updated,
        "errores": errors,
    }