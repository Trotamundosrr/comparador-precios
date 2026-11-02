from django.db.models import Count, Q
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .geo import parse_coordinates, stores_by_distance
from .models import Category, Store
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .comparador import ORDERS, absolute_url, build_comparison, lowest_prices
from .models import Category, Promotion, Store

from django.contrib.auth import authenticate
from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle

from .permissions import IsStoreAdmin

from .serializers import (
    CategoriaSerializer,
    LoginSerializer,
    MiTiendaSerializer,
    TiendaDetalleSerializer,
    TiendaListaSerializer,
    ArchivoSerializer,
)

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view

from .models import Category, Price, Product, Promotion, Store
from .search import search_products
from .serializers import (
    CategoriaSerializer,
    LoginSerializer,
    MiProductoEdicionSerializer,
    MiProductoEntradaSerializer,
    MiProductoSalidaSerializer,
    MiPromocionSerializer,
    MiTiendaSerializer,
    TiendaDetalleSerializer,
    TiendaListaSerializer,
)
from .services import upsert_store_product
from django.http import HttpResponse
from rest_framework.parsers import FormParser, MultiPartParser

from .importer import build_template, import_products, read_table

def read_coordinates(request, required=False):
    """Lee ?lat=&lng= de la URL. Devuelve (lat, lng) o None. Responde 400 si son inválidas."""
    lat = request.query_params.get("lat")
    lng = request.query_params.get("lng")
    if lat is None and lng is None:
        if required:
            raise ValidationError({"detail": "Este orden necesita los parámetros lat y lng."})
        return None
    coords = parse_coordinates(lat, lng)
    if coords is None:
        raise ValidationError({"detail": "lat y lng deben ser coordenadas válidas."})
    return coords


def stores_queryset():
    return Store.objects.filter(is_active=True).annotate(product_count=Count("prices"))


class CategoriaListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategoriaSerializer
    pagination_class = None          # son pocas, van todas juntas


class TiendaListView(generics.ListAPIView):
    serializer_class = TiendaListaSerializer

    def get_queryset(self):
        stores = stores_queryset()
        q = self.request.query_params.get("q", "").strip()
        if q:
            stores = stores.filter(Q(name__icontains=q) | Q(zone__icontains=q))
        coords = read_coordinates(self.request)
        if coords is None:
            return stores
        ordered = stores_by_distance(stores, *coords)
        for store, km in ordered:
            store.distance_km = km            # lo lee el serializer
        return [store for store, _ in ordered]


class TiendaDetalleView(generics.RetrieveAPIView):
    serializer_class = TiendaDetalleSerializer
    lookup_field = "slug"

    def get_queryset(self):
        return stores_queryset()

class ComparadorView(APIView):
    @extend_schema(parameters=[
        OpenApiParameter("q", str, description="Texto a buscar (exacto, parecido o sinónimo)"),
        OpenApiParameter("categoria", str, description="Slug de la categoría"),
        OpenApiParameter("orden", str, enum=list(ORDERS),
                         description="relevancia (por defecto con q), precio o cercania"),
        OpenApiParameter("lat", float, description="Latitud del usuario"),
        OpenApiParameter("lng", float, description="Longitud del usuario"),
    ])
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        categoria = request.query_params.get("categoria", "").strip()
        orden = request.query_params.get("orden") or ("relevancia" if q else "precio")
        if orden not in ORDERS:
            raise ValidationError({"detail": "orden debe ser: relevancia, precio o cercania."})
        if orden == "relevancia" and not q:
            orden = "precio"            # sin texto no hay relevancia que medir
        coords = read_coordinates(request, required=(orden == "cercania"))

        results = build_comparison(request, q, categoria, orden, coords)
        paginator = PageNumberPagination()
        page = paginator.paginate_queryset(results, request, view=self)
        return paginator.get_paginated_response(page)


class InicioView(APIView):
    def get(self, request):
        promos = list(
            Promotion.objects.active()
            .filter(store__is_active=True)
            .select_related("store", "product")
            .order_by("-created_at", "-id")[:10]
        )
        lowest = lowest_prices([p.product_id for p in promos if p.product_id])

        items = []
        for promo in promos:
            best = lowest.get(promo.product_id)
            items.append({
                "id": promo.id,
                "titulo": promo.title,
                "descripcion": promo.description,
                "precio_promo": promo.promo_price,
                "imagen": absolute_url(request, promo.image),
                "valida_hasta": promo.valid_until,
                "tienda": {
                    "nombre": promo.store.name, "slug": promo.store.slug,
                    "logo": absolute_url(request, promo.store.logo),
                },
                "producto": None if promo.product is None else {
                    "id": promo.product.id, "nombre": promo.product.name,
                    "presentacion": promo.product.unit,
                },
                # se recalcula en cada petición: siempre refleja los precios actuales
                "precio_mas_bajo": None if best is None else {
                    "precio": best[0],
                    "tienda": {"nombre": best[1].name, "slug": best[1].slug},
                },
            })
        return Response({
            "promociones_destacadas": items,
            "categorias": CategoriaSerializer(Category.objects.all(), many=True).data,
        })
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []          # para pedir un token no hace falta tener uno
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer)
    def post(self, request):
        data = LoginSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        user = authenticate(request, username=data.validated_data["username"],
                            password=data.validated_data["password"])
        if user is None:
            return Response({"detail": "Usuario o contraseña incorrectos."},
                            status=status.HTTP_401_UNAUTHORIZED)
        store = getattr(user, "store", None)
        if store is None or not store.is_active:
            return Response({"detail": "Esta cuenta no administra ninguna tienda activa."},
                            status=status.HTTP_403_FORBIDDEN)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key,
                         "tienda": {"nombre": store.name, "slug": store.slug}})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsStoreAdmin]

    def get(self, request):
        store = request.user.store
        return Response({"usuario": request.user.username,
                         "tienda": {"nombre": store.name, "slug": store.slug}})


class MiTiendaView(generics.RetrieveUpdateAPIView):
    serializer_class = MiTiendaSerializer
    permission_classes = [IsStoreAdmin]
    http_method_names = ["get", "patch", "head", "options"]    # leer y editar parcialmente

    def get_object(self):
        return self.request.user.store      # la tienda sale del token, no de la URL

@extend_schema_view(
    get=extend_schema(parameters=[
        OpenApiParameter("q", str, description="Buscar entre mis productos (tolera errores de tipeo)"),
        OpenApiParameter("categoria", str, description="Slug de categoría"),
    ]),
    post=extend_schema(request=MiProductoEntradaSerializer,
                       responses={201: MiProductoSalidaSerializer}),
)
class MisProductosView(generics.ListCreateAPIView):
    permission_classes = [IsStoreAdmin]
    serializer_class = MiProductoSalidaSerializer

    def get_queryset(self):
        store = self.request.user.store          # solo MI tienda
        prices = (Price.objects.filter(store=store)
                  .select_related("product", "product__category")
                  .order_by("product__name"))
        q = self.request.query_params.get("q", "").strip()
        if q:
            mine = Product.objects.filter(prices__store=store)
            ids = [p.id for p, _, _ in search_products(mine, q, limit=500)]
            prices = prices.filter(product_id__in=ids)
        categoria = self.request.query_params.get("categoria", "").strip()
        if categoria:
            prices = prices.filter(product__category__slug=categoria)
        return prices

    def create(self, request, *args, **kwargs):
        data = MiProductoEntradaSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        v = data.validated_data
        existing = Product.objects.get(pk=v["producto_id"]) if v.get("producto_id") else None
        price, created = upsert_store_product(
            request.user.store, product=existing, amount=v["precio"],
            name=v.get("nombre", ""), brand=v["marca"], unit=v["presentacion"],
            category=v.get("category"), barcode=v["codigo_barras"],
            image=v.get("imagen"), available=v["disponible"])
        out = MiProductoSalidaSerializer(price, context=self.get_serializer_context()).data
        return Response(out, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@extend_schema_view(patch=extend_schema(request=MiProductoEdicionSerializer,
                                        responses=MiProductoSalidaSerializer))
class MiProductoDetalleView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsStoreAdmin]
    serializer_class = MiProductoSalidaSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return (Price.objects.filter(store=self.request.user.store)      # solo MIS precios
                .select_related("product", "product__category"))

    def update(self, request, *args, **kwargs):
        price = self.get_object()
        serializer = MiProductoEdicionSerializer(price, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MiProductoSalidaSerializer(price, context=self.get_serializer_context()).data)


class SugerenciasProductoView(APIView):
    """'¿Es este tu producto?': productos del catálogo parecidos a lo que se está escribiendo."""
    permission_classes = [IsStoreAdmin]

    @extend_schema(parameters=[OpenApiParameter("q", str)])
    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if len(q) < 2:
            return Response([])
        found = search_products(Product.objects.select_related("category"), q, limit=8)
        return Response([{
            "id": p.id, "nombre": p.name, "marca": p.brand, "presentacion": p.unit,
            "categoria": p.category.name if p.category else None,
            "codigo_barras": p.barcode,
        } for p, _, _ in found])


@extend_schema_view(get=extend_schema(parameters=[
    OpenApiParameter("vigentes", str, description="Pon 1 para ver solo las vigentes")]))
class MisPromocionesView(generics.ListCreateAPIView):
    permission_classes = [IsStoreAdmin]
    serializer_class = MiPromocionSerializer

    def get_queryset(self):
        promos = Promotion.objects.filter(store=self.request.user.store).order_by("-created_at", "-id")
        if self.request.query_params.get("vigentes") == "1":
            promos = promos.active()
        return promos

    def perform_create(self, serializer):
        serializer.save(store=self.request.user.store)      # la tienda sale del token, nunca del JSON


class MiPromocionDetalleView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsStoreAdmin]
    serializer_class = MiPromocionSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return Promotion.objects.filter(store=self.request.user.store)
    
class PlantillaView(APIView):
    permission_classes = [IsStoreAdmin]

    def get(self, request):
        content = build_template().getvalue()
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="plantilla_productos.xlsx"'
        return response

class ImportarView(APIView):
    permission_classes = [IsStoreAdmin]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request={
            "multipart/form-data": {
                "type": "object",
                "properties": {
                    "archivo": {"type": "string", "format": "binary"},
                },
                "required": ["archivo"],
            }
        }
    )
    def post(self, request):
        data = ArchivoSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        uploaded = data.validated_data["archivo"]
        try:
            rows = read_table(uploaded)
        except ValueError as exc:
            return Response({"archivo": [str(exc)]}, status=400)
        return Response(import_products(request.user.store, rows))