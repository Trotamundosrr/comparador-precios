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