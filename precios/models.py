import secrets


from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from .texto import normalize


class Category(models.Model):
    name = models.CharField("nombre", max_length=100, unique=True)
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Store(models.Model):
    # Si el usuario tiene tienda, es adminTienda
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="store",
    )
    name = models.CharField("nombre", max_length=120, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField("descripción", blank=True)
    zone = models.CharField("zona", max_length=100, blank=True)
    address = models.CharField("dirección", max_length=200, blank=True)
    latitude = models.FloatField("latitud", help_text="Ej. -17.3939")
    longitude = models.FloatField("longitud", help_text="Ej. -66.1568")
    whatsapp = models.CharField(max_length=20, blank=True)
    hours = models.CharField("horarios", max_length=120, blank=True)
    logo = models.ImageField(upload_to="tiendas/logos/", blank=True)
    cover = models.ImageField("portada", upload_to="tiendas/portadas/", blank=True)
    primary_color = models.CharField("color principal", max_length=7, default="#1f7a4d")
    is_active = models.BooleanField("activa", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tienda"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField("nombre", max_length=200)
    brand = models.CharField("marca", max_length=100, blank=True)
    unit = models.CharField("presentación", max_length=50, blank=True)
    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="products",
    )
    barcode = models.CharField("código de barras", max_length=20, blank=True, db_index=True)
    search_text = models.CharField(max_length=400, default="", blank=True,
                                   editable=False, db_index=True)
    match_key = models.CharField(max_length=300, default="", blank=True,
                                 editable=False, db_index=True)
    
    class Meta:
        verbose_name = "producto"
        unique_together = [("name", "brand", "unit")]
        ordering = ["name"]
    def save(self, *args, **kwargs):
        category = self.category.name if self.category else ""
        self.search_text = normalize(f"{self.name} {self.brand} {self.unit} {category}")
        self.match_key = normalize(f"{self.name} {self.brand} {self.unit}")
        super().save(*args, **kwargs)
    def __str__(self):
        return f"{self.name} {self.brand} {self.unit}".strip()


class Price(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="prices")
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="prices")
    amount = models.DecimalField("precio (Bs)", max_digits=10, decimal_places=2)
    image = models.ImageField("imagen", upload_to="precios/", blank=True)
    available = models.BooleanField("disponible", default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "precio"
        unique_together = [("product", "store")]
        ordering = ["amount"]

    def __str__(self):
        return f"{self.product} en {self.store}: Bs {self.amount}"

class PromotionQuerySet(models.QuerySet):
    def active(self):
        """Promociones vigentes hoy."""
        today = timezone.localdate()
        return self.filter(valid_from__lte=today).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )

class Promotion(models.Model):
    objects = PromotionQuerySet.as_manager()
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="promotions")
    product = models.ForeignKey(
        Product, null=True, blank=True,
        on_delete=models.CASCADE, related_name="promotions",
    )
    title = models.CharField("título", max_length=150)
    description = models.CharField("detalle", max_length=300, blank=True)
    promo_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField("imagen", upload_to="promociones/", blank=True)
    valid_from = models.DateField("válida desde", default=timezone.localdate)
    valid_until = models.DateField("válida hasta", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "promoción"
        verbose_name_plural = "promociones"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.store})"
class Synonym(models.Model):
    terms = models.CharField("términos", max_length=300,
                             help_text="Separados por coma. Ej: gaseosa, refresco, soda")

    class Meta:
        verbose_name = "sinónimo"

    def __str__(self):
        return self.terms

class PromotionQuerySet(models.QuerySet):
    def active(self):
        """Promociones vigentes hoy."""
        today = timezone.localdate()
        return self.filter(valid_from__lte=today).filter(
            Q(valid_until__isnull=True) | Q(valid_until__gte=today)
        )

class Reservation(models.Model):
    """Reserva de un producto en una tienda (el cliente no necesita cuenta)."""
    STATUS = [
        ("pendiente", "Pendiente"),
        ("confirmada", "Confirmada"),
        ("entregada", "Entregada"),
        ("cancelada", "Cancelada"),
    ]
    CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin 0/O ni 1/I

    code = models.CharField("código", max_length=8, unique=True, editable=False)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, related_name="reservations")
    product = models.ForeignKey(Product, null=True, on_delete=models.SET_NULL,
                                related_name="reservations")
    product_name = models.CharField("producto", max_length=250)     # copia por si se borra
    unit_price = models.DecimalField("precio unitario (Bs)", max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField("cantidad", default=1)
    customer_name = models.CharField("cliente", max_length=120)
    customer_phone = models.CharField("teléfono", max_length=20)
    status = models.CharField("estado", max_length=12, choices=STATUS, default="pendiente")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "reserva"
        ordering = ["-created_at"]

    @property
    def total(self):
        return self.unit_price * self.quantity

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                code = "".join(secrets.choice(self.CODE_ALPHABET) for _ in range(8))
                if not Reservation.objects.filter(code=code).exists():
                    self.code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} - {self.product_name} x{self.quantity}"    