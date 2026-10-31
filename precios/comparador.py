from django.db.models import Prefetch

from .geo import haversine_km
from .models import Price, Product, Promotion
from .search import search_products

ORDERS = ("relevancia", "precio", "cercania")


def absolute_url(request, file):
    """URL completa de un archivo subido, o None si no hay archivo."""
    return request.build_absolute_uri(file.url) if file else None


def _promo_value(promo):
    return promo.promo_price if promo.promo_price is not None else float("inf")


def _best_promotions(product_ids):
    """{(id_tienda, id_producto): la promoción vigente más barata}"""
    best = {}
    promos = Promotion.objects.active().filter(product_id__in=product_ids, store__is_active=True)
    for promo in promos.order_by("-created_at", "-id"):
        key = (promo.store_id, promo.product_id)
        if key not in best or _promo_value(promo) < _promo_value(best[key]):
            best[key] = promo
    return best


def _effective_price(price, promo):
    """Precio que realmente se paga: el de la promoción si existe y es menor."""
    if promo is not None and promo.promo_price is not None and promo.promo_price < price.amount:
        return promo.promo_price
    return price.amount


def lowest_prices(product_ids):
    """{id_producto: (precio_efectivo, tienda)} con el precio más bajo actual."""
    prices = Price.objects.filter(
        product_id__in=product_ids, available=True, store__is_active=True
    ).select_related("store")
    promos = _best_promotions(product_ids)
    best = {}
    for price in prices:
        effective = _effective_price(price, promos.get((price.store_id, price.product_id)))
        current = best.get(price.product_id)
        if current is None or effective < current[0]:
            best[price.product_id] = (effective, price.store)
    return best


def build_comparison(request, q, categoria, orden, coords):
    active_prices = Price.objects.filter(
        available=True, store__is_active=True).select_related("store")
    products = Product.objects.select_related("category").prefetch_related(
        Prefetch("prices", queryset=active_prices, to_attr="active_prices"))
    if categoria:
        products = products.filter(category__slug=categoria)

    if q:
        matches = search_products(products, q, limit=200)      # [(producto, tipo, puntaje)]
    else:
        matches = [(p, "", 0) for p in products]
    matches = [m for m in matches if m[0].active_prices]       # solo con precios vigentes

    promos = _best_promotions([m[0].id for m in matches])
    entries = []
    for product, kind, score in matches:
        rows = []
        for price in product.active_prices:
            promo = promos.get((price.store_id, product.id))
            distance = None
            if coords:
                distance = haversine_km(coords[0], coords[1],
                                        price.store.latitude, price.store.longitude)
            rows.append({"price": price, "promo": promo,
                         "effective": _effective_price(price, promo), "distance": distance})

        minimum = min(r["effective"] for r in rows)
        maximum = max(r["effective"] for r in rows)
        by_price = sorted(rows, key=lambda r: r["effective"])
        if orden == "cercania":
            rows = sorted(rows, key=lambda r: (r["distance"], r["effective"]))
        else:
            rows = by_price
        nearest = min(r["distance"] for r in rows) if coords else None
        image = next((r["price"].image for r in by_price if r["price"].image), None)

        result = {
            "producto": {
                "id": product.id, "nombre": product.name, "marca": product.brand,
                "presentacion": product.unit,
                "categoria": product.category.name if product.category else None,
                "imagen": absolute_url(request, image),
            },
            "coincidencia": kind or None,
            "puntaje": score,
            "precio_minimo": minimum,
            "ahorro_maximo": maximum - minimum,
            "precios": [{
                "tienda": {
                    "nombre": r["price"].store.name, "slug": r["price"].store.slug,
                    "logo": absolute_url(request, r["price"].store.logo),
                    "distancia_km": None if r["distance"] is None else round(r["distance"], 2),
                },
                "precio": r["price"].amount,
                "precio_efectivo": r["effective"],
                "actualizado": r["price"].updated_at,
                "es_mas_barato": r["effective"] == minimum,
                "promocion": None if r["promo"] is None else {
                    "titulo": r["promo"].title,
                    "precio_promo": r["promo"].promo_price,
                    "valida_hasta": r["promo"].valid_until,
                },
            } for r in rows],
        }
        entries.append((result, nearest))

    # sort() es estable: los empates conservan el orden de relevancia
    if orden == "cercania":
        entries.sort(key=lambda e: e[1])
    elif orden == "precio":
        entries.sort(key=lambda e: e[0]["precio_minimo"])
    return [e[0] for e in entries]