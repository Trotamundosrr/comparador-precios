import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from precios.models import Category, Price, Product, Promotion, Store

# Tiendas FICTICIAS. Ubicaciones aproximadas dentro de Cochabamba.
# (nombre, zona, dirección, latitud, longitud, color)
STORES = [
    ("Abarrotes Doña Lucía", "Cala Cala", "Calle de ejemplo 101", -17.3745, -66.1575, "#1f7a4d"),
    ("Tienda Don Mario", "Sarco", "Calle de ejemplo 202", -17.3830, -66.1440, "#c0392b"),
    ("Minimarket El Ahorro", "Queru Queru", "Calle de ejemplo 303", -17.3770, -66.1690, "#2c5aa0"),
    ("Víveres La Esquina", "Recoleta", "Calle de ejemplo 404", -17.4040, -66.1520, "#8e44ad"),
    ("Mercadito San Miguel", "Muyurina", "Calle de ejemplo 505", -17.4120, -66.1330, "#d35400"),
    ("Tienda Familiar Los Pinos", "Av. América", "Calle de ejemplo 606", -17.3780, -66.1620, "#16a085"),
]

# (categoría, nombre, marca, presentación, precio base en Bs). Precios ficticios de referencia.
PRODUCTS = [
    ("Lácteos", "Leche entera", "PIL", "900 ml", 10.50),
    ("Lácteos", "Yogurt natural", "PIL", "1 L", 17.00),
    ("Lácteos", "Queso criollo", "", "500 g", 35.00),
    ("Lácteos", "Mantequilla", "PIL", "200 g", 14.00),
    ("Abarrotes", "Azúcar blanca", "Guabirá", "1 kg", 7.50),
    ("Abarrotes", "Aceite vegetal", "Fino", "900 ml", 18.90),
    ("Abarrotes", "Arroz grano de oro", "", "1 kg", 9.20),
    ("Abarrotes", "Fideo spaghetti", "Dorina", "400 g", 6.80),
    ("Abarrotes", "Lenteja", "", "500 g", 12.00),
    ("Abarrotes", "Frejol", "", "500 g", 14.00),
    ("Abarrotes", "Quinua", "", "500 g", 25.00),
    ("Abarrotes", "Avena", "", "400 g", 9.00),
    ("Abarrotes", "Café instantáneo", "Nescafé", "170 g", 38.00),
    ("Bebidas", "Gaseosa cola", "Coca-Cola", "2 L", 12.00),
    ("Bebidas", "Gaseosa cola", "Pepsi", "2 L", 11.50),
    ("Bebidas", "Agua mineral", "Vital", "2 L", 6.00),
    ("Bebidas", "Jugo de naranja", "Del Valle", "1 L", 12.00),
    ("Frutas y verduras", "Papa", "", "1 kg", 6.00),
    ("Frutas y verduras", "Cebolla", "", "1 kg", 8.00),
    ("Frutas y verduras", "Tomate", "", "1 kg", 9.00),
    ("Frutas y verduras", "Zanahoria", "", "1 kg", 5.00),
    ("Frutas y verduras", "Plátano", "", "1 kg", 7.00),
    ("Carnes y huevos", "Pollo entero", "", "1 kg", 21.00),
    ("Carnes y huevos", "Carne molida", "", "1 kg", 52.00),
    ("Carnes y huevos", "Huevo", "", "Maple 30 un", 32.00),
    ("Limpieza", "Detergente en polvo", "Ola", "800 g", 22.00),
    ("Limpieza", "Papel higiénico", "Elite", "4 rollos", 14.50),
    ("Limpieza", "Lavandina", "", "1 L", 8.00),
    ("Limpieza", "Jabón en barra", "", "3 un", 9.00),
    ("Cuidado personal", "Pasta dental", "Colgate", "90 g", 12.00),
]


class Command(BaseCommand):
    help = "Carga tiendas, productos, precios y promociones de ejemplo (datos ficticios)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Borra TODOS los datos del comparador antes de cargar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(42)  # misma semilla = mismos datos siempre
        if options["reset"]:
            self.reset()
        categories = self.create_categories()
        products = self.create_products(categories)
        stores = self.create_stores()
        self.create_prices(rng, products, stores)
        self.create_promotions(rng, stores)
        self.stdout.write(self.style.SUCCESS(
            f"Listo: {Store.objects.count()} tiendas, {Product.objects.count()} productos, "
            f"{Price.objects.count()} precios, {Promotion.objects.count()} promociones."
        ))
        self.stdout.write("Usuarios adminTienda: demo_tienda1 ... demo_tienda6 / contraseña: demo1234")

    def reset(self):
        Promotion.objects.all().delete()
        Price.objects.all().delete()
        Product.objects.all().delete()
        Store.objects.all().delete()
        Category.objects.all().delete()
        get_user_model().objects.filter(username__startswith="demo_").delete()

    def create_categories(self):
        categories = {}
        for name in sorted({p[0] for p in PRODUCTS}):
            categories[name], _ = Category.objects.get_or_create(
                name=name, defaults={"slug": slugify(name)})
        return categories

    def create_products(self, categories):
        products = []
        for cat, name, brand, unit, base in PRODUCTS:
            product, _ = Product.objects.get_or_create(
                name=name, brand=brand, unit=unit, defaults={"category": categories[cat]})
            products.append((product, base))
        return products

    def create_stores(self):
        User = get_user_model()
        stores = []
        for i, (name, zone, address, lat, lng, color) in enumerate(STORES, start=1):
            user, created = User.objects.get_or_create(username=f"demo_tienda{i}")
            if created:
                user.set_password("demo1234")
                user.save()
            store, _ = Store.objects.update_or_create(
                slug=slugify(name),
                defaults={
                    "name": name, "zone": zone, "address": address,
                    "latitude": lat, "longitude": lng, "primary_color": color,
                    "description": f"Tienda de barrio en {zone}. Datos de ejemplo.",
                    "hours": "Lun-Sáb 8:00-21:00 · Dom 9:00-14:00",
                    "whatsapp": f"5917000000{i}",   # número ficticio
                    "owner": user,
                },
            )
            stores.append(store)
        return stores

    def create_prices(self, rng, products, stores):
        for product, base in products:
            # cada producto está en entre 3 y todas las tiendas
            for store in rng.sample(stores, rng.randint(3, len(stores))):
                raw = base * rng.uniform(0.92, 1.10)
                amount = Decimal(str(round(raw * 10) / 10)).quantize(Decimal("0.01"))
                Price.objects.update_or_create(
                    product=product, store=store, defaults={"amount": amount})

    def create_promotions(self, rng, stores):
        now = timezone.now()
        today = timezone.localdate()
        prices = list(Price.objects.select_related("product", "store").order_by("id"))
        for i, price in enumerate(rng.sample(prices, 10)):
            promo, _ = Promotion.objects.get_or_create(
                store=price.store, product=price.product,
                title=f"Oferta: {price.product.name}",
                defaults={
                    "description": "Hasta agotar stock",
                    "promo_price": (price.amount * Decimal("0.85")).quantize(Decimal("0.01")),
                    "valid_until": today + timedelta(days=rng.randint(2, 10)),
                },
            )
            # created_at es automático; con update() lo escalonamos para probar el orden
            Promotion.objects.filter(pk=promo.pk).update(created_at=now - timedelta(hours=6 * i))
        for store in stores[:2]:
            Promotion.objects.get_or_create(
                store=store, title="Delivery gratis desde Bs 100",
                defaults={"valid_until": today + timedelta(days=15)},
            )