from django.db import transaction

from .models import Price, Product
from .texto import normalize


def find_or_create_product(name, brand="", unit="", category=None, barcode=""):
    """Reutiliza un producto del catálogo (por código de barras o por nombre+marca+presentación)
    o crea uno nuevo. Devuelve (producto, creado)."""
    barcode = (barcode or "").strip()
    product = None
    if barcode:
        product = Product.objects.filter(barcode=barcode).first()
    if product is None:
        key = normalize(f"{name} {brand} {unit}")
        product = Product.objects.filter(match_key=key).first()
    if product is not None:
        if category is not None and product.category_id is None:
            product.category = category          # completa la categoría si faltaba
            product.save()
        return product, False
    product = Product.objects.create(
        name=name.strip(), brand=brand.strip(), unit=unit.strip(),
        category=category, barcode=barcode)
    return product, True


@transaction.atomic
def upsert_store_product(store, *, amount, product=None, name="", brand="", unit="",
                         category=None, barcode="", image=None, available=True):
    """Pone un producto en la tienda con su precio. Si ya lo tenía, actualiza.
    La usan el formulario del panel y (más adelante) la carga por Excel.
    Devuelve (precio, creado)."""
    if product is None:
        product, _ = find_or_create_product(name, brand, unit, category, barcode)
    price = Price.objects.filter(product=product, store=store).first()
    created = price is None
    if created:
        price = Price(product=product, store=store)
    price.amount = amount
    price.available = available
    if image is not None:
        price.image = image
    price.save()
    return price, created