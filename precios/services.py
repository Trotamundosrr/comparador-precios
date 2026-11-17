from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from .models import Price, Product, Promotion
from .texto import normalize


class ProductoCompartido(APIException):
    status_code = 409
    default_code = "producto_compartido"
    default_detail = ("Otras tiendas también venden este producto, así que no puedes cambiar "
                      "sus datos. Puedes cambiar tu precio, disponibilidad e imagen. Si el dato "
                      "está mal, quítalo de tu tienda y cárgalo de nuevo, o pide la corrección.")


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
    La usan el formulario del panel y la carga por Excel.
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


_SIN_CAMBIO = object()      # distingue "no mandó imagen" de "mandó null (quitar imagen)"
CATALOG_FIELDS = {"nombre": "name", "marca": "brand", "presentacion": "unit",
                  "category": "category", "codigo_barras": "barcode"}


def _delete_file(name):
    """Borra un archivo de media/ (Django no lo hace solo al reemplazar o borrar)."""
    if name:
        Price._meta.get_field("image").storage.delete(name)


def _update_catalog(price, data):
    """Cambia datos del producto del catálogo. Solo si esta tienda es la única que lo vende."""
    product = price.product
    new = {attr: data[key] for key, attr in CATALOG_FIELDS.items() if key in data}
    if "category" in new:
        changed = new["category"] != product.category
    else:
        changed = False
    changed = changed or any(
        str(new[a]).strip() != getattr(product, a) for a in ("name", "brand", "unit", "barcode")
        if a in new)
    if not changed:
        return

    if Price.objects.filter(product=product).exclude(store=price.store).exists():
        raise ProductoCompartido()

    for attr, value in new.items():
        setattr(product, attr, value.strip() if isinstance(value, str) else value)

    twin = Product.objects.filter(match_key=normalize(f"{product.name} {product.brand} {product.unit}")
                                  ).exclude(pk=product.pk).first()
    if twin:
        raise ValidationError({"nombre": [
            f"Ya existe en el catálogo «{twin}» (producto_id {twin.id}). "
            "Quita este producto y vincula ese con su producto_id."]})
    if product.barcode:
        other = Product.objects.filter(barcode=product.barcode).exclude(pk=product.pk).first()
        if other:
            raise ValidationError({"codigo_barras": [
                f"Ese código de barras ya pertenece a «{other}» (producto_id {other.id})."]})
    product.save()                         # recalcula search_text y match_key


@transaction.atomic
def update_store_product(price, data):
    """PATCH de un producto de la tienda. `data` es el validated_data del serializer de edición.
    Aplica todo o nada."""
    _update_catalog(price, data)

    if "precio" in data:
        today = timezone.localdate()
        clash = (Promotion.objects
                 .filter(store=price.store, product=price.product, promo_price__gte=data["precio"])
                 .filter(Q(valid_until__isnull=True) | Q(valid_until__gte=today)).first())
        if clash:
            raise ValidationError({"precio": [
                f"Tu promoción «{clash.title}» tiene precio Bs {clash.promo_price}, que no sería "
                "menor al nuevo precio. Ajusta o elimina la promoción primero."]})
        price.amount = data["precio"]
    if "disponible" in data:
        price.available = data["disponible"]

    old_image = None
    if data.get("imagen", _SIN_CAMBIO) is not _SIN_CAMBIO:
        old_image = price.image.name
        price.image = data["imagen"] or ""
    price.save()
    if old_image and old_image != price.image.name:
        _delete_file(old_image)
    return price


@transaction.atomic
def remove_store_product(price):
    """Quita un producto de MI tienda: su precio, mis promociones de ese producto y las imágenes.
    Si ninguna otra tienda lo vende, también sale del catálogo (así no queda basura en las sugerencias).
    Devuelve cuántas promociones se eliminaron."""
    product, store = price.product, price.store
    promos = list(Promotion.objects.filter(store=store, product=product))
    files = [price.image.name] + [p.image.name for p in promos]
    for promo in promos:
        promo.delete()
    price.delete()
    for name in files:
        _delete_file(name)
    if not product.prices.exists() and not product.promotions.exists():
        product.delete()
    return len(promos)