from rest_framework import serializers

from .models import Category, Promotion, Store


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