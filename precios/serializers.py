from rest_framework import serializers

from .models import Category, Promotion, Store
from decimal import Decimal

from .models import Category, Price, Product, Promotion, Store


class CategoriaSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="name")

    class Meta:
        model = Category
        fields = ["id", "nombre", "slug"]


class PromocionSerializer(serializers.ModelSerializer):
    titulo = serializers.CharField(source="title")
    descripcion = serializers.CharField(source="description")
    precio_promo = serializers.DecimalField(source="promo_price", max_digits=10, decimal_places=2)
    imagen = serializers.ImageField(source="image")
    valida_hasta = serializers.DateField(source="valid_until")
    producto = serializers.IntegerField(source="product_id")

    class Meta:
        model = Promotion
        fields = ["id", "titulo", "descripcion", "precio_promo", "imagen", "valida_hasta", "producto"]


class TiendaListaSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="name")
    zona = serializers.CharField(source="zone")
    direccion = serializers.CharField(source="address")
    latitud = serializers.FloatField(source="latitude")
    longitud = serializers.FloatField(source="longitude")
    logo = serializers.ImageField()
    portada = serializers.ImageField(source="cover")
    cantidad_productos = serializers.IntegerField(source="product_count")
    distancia_km = serializers.SerializerMethodField()

    class Meta:
        model = Store
        fields = ["slug", "nombre", "zona", "direccion", "latitud", "longitud",
                  "logo", "portada", "cantidad_productos", "distancia_km"]

    def get_distancia_km(self, store):
        km = getattr(store, "distance_km", None)   # la vista lo agrega si hay coordenadas
        return None if km is None else round(km, 2)


class TiendaDetalleSerializer(TiendaListaSerializer):
    descripcion = serializers.CharField(source="description")
    horarios = serializers.CharField(source="hours")
    whatsapp = serializers.CharField()
    tema = serializers.SerializerMethodField()
    promociones = serializers.SerializerMethodField()

    class Meta(TiendaListaSerializer.Meta):
        fields = TiendaListaSerializer.Meta.fields + [
            "descripcion", "horarios", "whatsapp", "tema", "promociones"]

    def get_tema(self, store):
        request = self.context["request"]

        def url(file):
            return request.build_absolute_uri(file.url) if file else None

        return {"color_principal": store.primary_color,
                "logo": url(store.logo), "portada": url(store.cover)}

    def get_promociones(self, store):
        return PromocionSerializer(
            store.promotions.active(), many=True, context=self.context).data
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class MiTiendaSerializer(serializers.ModelSerializer):
    nombre = serializers.CharField(source="name", max_length=120)
    descripcion = serializers.CharField(source="description", required=False, allow_blank=True)
    zona = serializers.CharField(source="zone", required=False, allow_blank=True, max_length=100)
    direccion = serializers.CharField(source="address", required=False, allow_blank=True, max_length=200)
    latitud = serializers.FloatField(source="latitude", min_value=-90, max_value=90)
    longitud = serializers.FloatField(source="longitude", min_value=-180, max_value=180)
    whatsapp = serializers.RegexField(
        r"^\+?\d{7,15}$", required=False, allow_blank=True,
        error_messages={"invalid": "Debe tener solo números (7 a 15 dígitos)."})
    horarios = serializers.CharField(source="hours", required=False, allow_blank=True, max_length=120)
    color_principal = serializers.RegexField(
        r"^#[0-9a-fA-F]{6}$", source="primary_color",
        error_messages={"invalid": "Debe ser un color como #1f7a4d."})
    logo = serializers.ImageField(required=False, allow_null=True)
    portada = serializers.ImageField(source="cover", required=False, allow_null=True)

    class Meta:
        model = Store
        fields = ["slug", "nombre", "descripcion", "zona", "direccion", "latitud", "longitud",
                  "whatsapp", "horarios", "color_principal", "logo", "portada"]
        read_only_fields = ["slug"]

    def validate_nombre(self, value):
        value = value.strip()
        if Store.objects.exclude(pk=self.instance.pk).filter(name__iexact=value).exists():
            raise serializers.ValidationError("Ya existe una tienda con ese nombre.")
        return value

class MiProductoSalidaSerializer(serializers.ModelSerializer):
    """Cómo se ve un producto de MI tienda (sale en listas y respuestas)."""
    producto_id = serializers.IntegerField(source="product_id")
    nombre = serializers.CharField(source="product.name")
    marca = serializers.CharField(source="product.brand")
    presentacion = serializers.CharField(source="product.unit")
    categoria = serializers.SerializerMethodField()
    codigo_barras = serializers.CharField(source="product.barcode")
    precio = serializers.DecimalField(source="amount", max_digits=10, decimal_places=2)
    imagen = serializers.ImageField(source="image")
    disponible = serializers.BooleanField(source="available")
    actualizado = serializers.DateTimeField(source="updated_at")

    class Meta:
        model = Price
        fields = ["id", "producto_id", "nombre", "marca", "presentacion", "categoria",
                  "codigo_barras", "precio", "imagen", "disponible", "actualizado"]

    def get_categoria(self, price):
        category = price.product.category
        return category.name if category else None


class MiProductoEntradaSerializer(serializers.Serializer):
    """Datos que llegan del formulario de 'agregar producto'."""
    producto_id = serializers.IntegerField(required=False)
    nombre = serializers.CharField(max_length=200, required=False)
    marca = serializers.CharField(max_length=100, allow_blank=True, default="")
    presentacion = serializers.CharField(max_length=50, allow_blank=True, default="")
    categoria = serializers.SlugField(allow_blank=True, default="")
    codigo_barras = serializers.RegexField(
        r"^\d{8,14}$", allow_blank=True, default="",
        error_messages={"invalid": "Debe tener entre 8 y 14 dígitos."})
    precio = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    imagen = serializers.ImageField(required=False)
    disponible = serializers.BooleanField(default=True)

    def validate(self, attrs):
        if not attrs.get("producto_id") and not attrs.get("nombre", "").strip():
            raise serializers.ValidationError("Envía el nombre del producto o un producto_id.")
        if attrs.get("producto_id") and not Product.objects.filter(pk=attrs["producto_id"]).exists():
            raise serializers.ValidationError({"producto_id": "Ese producto no existe."})
        slug = attrs.get("categoria")
        if slug:
            category = Category.objects.filter(slug=slug).first()
            if category is None:
                raise serializers.ValidationError({"categoria": "Esa categoría no existe."})
            attrs["category"] = category
        return attrs


class MiProductoEdicionSerializer(serializers.ModelSerializer):
    """Lo único que una tienda puede cambiar de un producto ya cargado."""
    precio = serializers.DecimalField(source="amount", max_digits=10, decimal_places=2,
                                      min_value=Decimal("0.01"))
    disponible = serializers.BooleanField(source="available")
    imagen = serializers.ImageField(source="image", allow_null=True)   # null = quitar la imagen

    class Meta:
        model = Price
        fields = ["precio", "disponible", "imagen"]


class MiPromocionSerializer(serializers.ModelSerializer):
    titulo = serializers.CharField(source="title", max_length=150)
    descripcion = serializers.CharField(source="description", required=False,
                                        allow_blank=True, max_length=300)
    precio_promo = serializers.DecimalField(
        source="promo_price", max_digits=10, decimal_places=2,
        min_value=Decimal("0.01"), required=False, allow_null=True)
    imagen = serializers.ImageField(source="image", required=False, allow_null=True)
    valida_desde = serializers.DateField(source="valid_from", required=False)
    valida_hasta = serializers.DateField(source="valid_until", required=False, allow_null=True)
    producto = serializers.IntegerField(source="product_id", required=False, allow_null=True)

    class Meta:
        model = Promotion
        fields = ["id", "titulo", "descripcion", "precio_promo", "imagen",
                "valida_desde", "valida_hasta", "producto"]

    def validate(self, attrs):
        store = self.context["request"].user.store
        current = self.instance
        product_id = attrs.get("product_id", getattr(current, "product_id", None))
        promo_price = attrs.get("promo_price", getattr(current, "promo_price", None))
        valid_from = attrs.get("valid_from", getattr(current, "valid_from", None))
        valid_until = attrs.get("valid_until", getattr(current, "valid_until", None))

        if product_id is not None:
            price = Price.objects.filter(store=store, product_id=product_id).first()
            if price is None:
                raise serializers.ValidationError(
                    {"producto": "Solo puedes hacer promociones de productos que vendes."})
            if promo_price is not None and promo_price >= price.amount:
                raise serializers.ValidationError(
                    {"precio_promo": f"Debe ser menor al precio normal (Bs {price.amount})."})
        if valid_from and valid_until and valid_until < valid_from:
            raise serializers.ValidationError(
                {"valida_hasta": "No puede ser anterior a la fecha de inicio."})
        return attrs
    
class ArchivoSerializer(serializers.Serializer):
    archivo = serializers.FileField()