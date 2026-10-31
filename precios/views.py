from django.db.models import Count, Q
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .geo import parse_coordinates, stores_by_distance
from .models import Category, Store
from .serializers import CategoriaSerializer, TiendaDetalleSerializer, TiendaListaSerializer

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from .comparador import ORDERS, absolute_url, build_comparison, lowest_prices
from .models import Category, Promotion, Store


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