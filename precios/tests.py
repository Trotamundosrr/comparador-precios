from django.test import TestCase

from .models import Category, Product, Synonym
from .search import search_products
from .texto import normalize
from .geo import directions_url, haversine_km, parse_coordinates, stores_by_distance
from .models import Store
from datetime import timedelta
from django.utils import timezone
from .models import Promotion

from decimal import Decimal

from .models import Category, Price, Product, Promotion, Store, Synonym

import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

class SearchTests(TestCase):
    def setUp(self):
        lacteos = Category.objects.create(name="Lácteos", slug="lacteos")
        bebidas = Category.objects.create(name="Bebidas", slug="bebidas")
        Product.objects.create(name="Leche entera", brand="PIL", unit="1 L", category=lacteos)
        Product.objects.create(name="Gaseosa cola", brand="Coca-Cola", unit="2 L", category=bebidas)
        Product.objects.create(name="Papa", unit="1 kg")
        Synonym.objects.create(terms="gaseosa, refresco, soda")
        Synonym.objects.create(terms="papa, patata")

    def nombres(self, consulta):
        return [p.name for p, _, _ in search_products(Product.objects.all(), consulta)]

    def test_normalize(self):
        self.assertEqual(normalize("  AZÚCAR  Blanca! "), "azucar blanca")

    def test_exacta(self):
        self.assertEqual(self.nombres("leche"), ["Leche entera"])

    def test_sin_tildes_ni_mayusculas(self):
        self.assertEqual(self.nombres("LÁCTEOS"), ["Leche entera"])

    def test_parcial(self):
        self.assertIn("Leche entera", self.nombres("lec"))

    def test_error_de_tipeo(self):
        self.assertIn("Leche entera", self.nombres("lehce"))

    def test_sinonimo(self):
        self.assertEqual(self.nombres("refresco"), ["Gaseosa cola"])
        self.assertEqual(self.nombres("patata"), ["Papa"])

    def test_sin_resultados(self):
        self.assertEqual(self.nombres("zzzxq"), [])
class GeoTests(TestCase):
    def test_distancia_cero(self):
        self.assertEqual(haversine_km(-17.39, -66.15, -17.39, -66.15), 0)

    def test_un_grado_de_longitud_en_el_ecuador(self):
        self.assertAlmostEqual(haversine_km(0, 0, 0, 1), 111.19, delta=0.1)

    def test_es_simetrica(self):
        a = haversine_km(-17.3938, -66.1570, -17.4120, -66.1330)
        b = haversine_km(-17.4120, -66.1330, -17.3938, -66.1570)
        self.assertAlmostEqual(a, b)

    def test_parse_coordinates(self):
        self.assertEqual(parse_coordinates("-17.39", "-66.15"), (-17.39, -66.15))
        self.assertIsNone(parse_coordinates("abc", "1"))
        self.assertIsNone(parse_coordinates("95", "0"))
        self.assertIsNone(parse_coordinates(None, None))

    def test_tiendas_ordenadas_por_cercania(self):
        Store.objects.create(name="Lejos", slug="lejos", latitude=-17.4120, longitude=-66.1330)
        Store.objects.create(name="Cerca", slug="cerca", latitude=-17.3940, longitude=-66.1572)
        ordenadas = stores_by_distance(Store.objects.all(), -17.3938, -66.1570)
        self.assertEqual([s.name for s, _ in ordenadas], ["Cerca", "Lejos"])
        self.assertLess(ordenadas[0][1], 0.1)

    def test_url_de_ruta(self):
        tienda = Store(name="X", slug="x", latitude=-17.39, longitude=-66.15)
        url = directions_url(tienda, -17.40, -66.16)
        self.assertIn("destination=-17.39,-66.15", url)
        self.assertIn("origin=-17.4,-66.16", url)
class TiendasApiTests(TestCase):
    def setUp(self):
        self.cerca = Store.objects.create(
            name="Cerca", slug="cerca", zone="Centro", latitude=-17.3940, longitude=-66.1572)
        self.lejos = Store.objects.create(
            name="Lejos", slug="lejos", zone="Sur", latitude=-17.4120, longitude=-66.1330)
        Store.objects.create(
            name="Inactiva", slug="inactiva", latitude=0, longitude=0, is_active=False)

    def test_lista_paginada_y_sin_inactivas(self):
        r = self.client.get("/api/tiendas/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)

    def test_orden_por_cercania(self):
        # el usuario está junto a "Lejos", así que esa debe salir primero
        r = self.client.get("/api/tiendas/", {"lat": -17.4118, "lng": -66.1331})
        resultados = r.json()["results"]
        self.assertEqual([t["nombre"] for t in resultados], ["Lejos", "Cerca"])
        self.assertIsNotNone(resultados[0]["distancia_km"])

    def test_coordenadas_invalidas(self):
        r = self.client.get("/api/tiendas/", {"lat": "abc", "lng": "1"})
        self.assertEqual(r.status_code, 400)

    def test_detalle_y_404(self):
        self.assertEqual(self.client.get("/api/tiendas/cerca/").status_code, 200)
        self.assertEqual(self.client.get("/api/tiendas/no-existe/").status_code, 404)
        self.assertEqual(self.client.get("/api/tiendas/inactiva/").status_code, 404)

    def test_solo_promociones_vigentes(self):
        hoy = timezone.localdate()
        Promotion.objects.create(store=self.cerca, title="Vigente", valid_until=hoy + timedelta(days=1))
        Promotion.objects.create(store=self.cerca, title="Vencida", valid_until=hoy - timedelta(days=1))
        Promotion.objects.create(store=self.cerca, title="Futura", valid_from=hoy + timedelta(days=3))
        r = self.client.get("/api/tiendas/cerca/").json()
        self.assertEqual([p["titulo"] for p in r["promociones"]], ["Vigente"])

class ComparadorApiTests(TestCase):
    def setUp(self):
        self.cerca = Store.objects.create(
            name="Cerca", slug="cerca", latitude=-17.3940, longitude=-66.1572)
        self.lejos = Store.objects.create(
            name="Lejos", slug="lejos", latitude=-17.4120, longitude=-66.1330)
        lacteos = Category.objects.create(name="Lácteos", slug="lacteos")
        self.leche = Product.objects.create(
            name="Leche entera", brand="PIL", unit="1 L", category=lacteos)
        self.arroz = Product.objects.create(name="Arroz", unit="1 kg")
        Price.objects.create(product=self.leche, store=self.cerca, amount=Decimal("9.00"))
        Price.objects.create(product=self.leche, store=self.lejos, amount=Decimal("8.00"))
        Price.objects.create(product=self.arroz, store=self.cerca, amount=Decimal("7.00"))

    def get(self, **params):
        return self.client.get("/api/comparador/", params)

    def test_busqueda_ordena_precios_y_marca_el_mas_barato(self):
        item = self.get(q="leche").json()["results"][0]
        self.assertEqual([p["tienda"]["slug"] for p in item["precios"]], ["lejos", "cerca"])
        self.assertTrue(item["precios"][0]["es_mas_barato"])
        self.assertFalse(item["precios"][1]["es_mas_barato"])
        self.assertEqual(item["precio_minimo"], 8.0)
        self.assertEqual(item["ahorro_maximo"], 1.0)

    def test_sinonimo(self):
        Synonym.objects.create(terms="arroz, grano")
        nombres = [i["producto"]["nombre"] for i in self.get(q="grano").json()["results"]]
        self.assertEqual(nombres, ["Arroz"])

    def test_cercania_exige_coordenadas(self):
        self.assertEqual(self.get(q="leche", orden="cercania").status_code, 400)

    def test_orden_por_cercania_dentro_del_producto(self):
        # el usuario está junto a "Cerca", aunque "Lejos" sea más barata
        r = self.get(q="leche", orden="cercania", lat=-17.3938, lng=-66.1570).json()
        precios = r["results"][0]["precios"]
        self.assertEqual([p["tienda"]["slug"] for p in precios], ["cerca", "lejos"])
        self.assertIsNotNone(precios[0]["tienda"]["distancia_km"])

    def test_orden_de_productos_por_precio(self):
        r = self.get(orden="precio").json()
        self.assertEqual([i["producto"]["nombre"] for i in r["results"]], ["Arroz", "Leche entera"])

    def test_promocion_vigente_cambia_el_precio_efectivo(self):
        Promotion.objects.create(
            store=self.cerca, product=self.leche, title="Oferta", promo_price=Decimal("6.50"))
        fila = self.get(q="leche").json()["results"][0]["precios"][0]
        self.assertEqual(fila["tienda"]["slug"], "cerca")
        self.assertEqual(fila["precio"], 9.0)
        self.assertEqual(fila["precio_efectivo"], 6.5)
        self.assertTrue(fila["es_mas_barato"])

    def test_filtro_por_categoria(self):
        nombres = [i["producto"]["nombre"] for i in self.get(categoria="lacteos").json()["results"]]
        self.assertEqual(nombres, ["Leche entera"])

    def test_precio_no_disponible_se_omite(self):
        Price.objects.filter(product=self.leche, store=self.lejos).update(available=False)
        item = self.get(q="leche").json()["results"][0]
        self.assertEqual(len(item["precios"]), 1)

    def test_orden_invalido(self):
        self.assertEqual(self.get(orden="magia").status_code, 400)

    def test_inicio_muestra_precio_mas_bajo_actualizado(self):
        Promotion.objects.create(store=self.cerca, product=self.leche, title="Oferta leche")
        promo = self.client.get("/api/inicio/").json()["promociones_destacadas"][0]
        self.assertEqual(promo["precio_mas_bajo"]["precio"], 8.0)
        # una tienda baja su precio y el carrusel se actualiza solo
        Price.objects.filter(product=self.leche, store=self.cerca).update(amount=Decimal("7.50"))
        promo = self.client.get("/api/inicio/").json()["promociones_destacadas"][0]
        self.assertEqual(promo["precio_mas_bajo"]["precio"], 7.5)
        self.assertEqual(promo["precio_mas_bajo"]["tienda"]["slug"], "cerca")

    def test_inicio_maximo_10_y_mas_recientes_primero(self):
        for i in range(12):
            Promotion.objects.create(store=self.cerca, title=f"P{i}")
        promos = self.client.get("/api/inicio/").json()["promociones_destacadas"]
        self.assertEqual(len(promos), 10)
        self.assertEqual(promos[0]["titulo"], "P11")

class AuthTests(TestCase):
    def setUp(self):
        cache.clear()      # reinicia el contador del límite de intentos de login
        User = get_user_model()
        self.duena = User.objects.create_user("duena", password="clave-segura-1")
        self.tienda = Store.objects.create(
            name="La Esquina", slug="la-esquina", owner=self.duena, latitude=-17.39, longitude=-66.15)
        vecino = User.objects.create_user("vecino", password="clave-segura-2")
        Store.objects.create(
            name="El Vecino", slug="el-vecino", owner=vecino, latitude=-17.40, longitude=-66.16)
        self.sin_tienda = User.objects.create_user("suelto", password="clave-segura-3")
        self.api = APIClient()

    def entrar(self, usuario, clave):
        return self.api.post("/api/auth/login/", {"username": usuario, "password": clave}, format="json")

    def con_token(self, usuario, clave):
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION="Token " + self.entrar(usuario, clave).json()["token"])
        return cliente

    def test_login_correcto(self):
        r = self.entrar("duena", "clave-segura-1")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["token"])
        self.assertEqual(r.json()["tienda"]["slug"], "la-esquina")

    def test_login_clave_incorrecta(self):
        self.assertEqual(self.entrar("duena", "mala").status_code, 401)

    def test_login_sin_tienda(self):
        self.assertEqual(self.entrar("suelto", "clave-segura-3").status_code, 403)

    def test_me(self):
        r = self.con_token("duena", "clave-segura-1").get("/api/auth/me/")
        self.assertEqual(r.json()["tienda"]["nombre"], "La Esquina")

    def test_mi_tienda_exige_token(self):
        self.assertEqual(self.api.get("/api/mi-tienda/").status_code, 401)

    def test_mi_tienda_exige_ser_dueno_de_tienda(self):
        token = Token.objects.create(user=self.sin_tienda)
        cliente = APIClient()
        cliente.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        self.assertEqual(cliente.get("/api/mi-tienda/").status_code, 403)

    def test_actualizar_perfil(self):
        cliente = self.con_token("duena", "clave-segura-1")
        r = cliente.patch("/api/mi-tienda/",
                          {"descripcion": "Abarrotes y más", "horarios": "Lun-Sáb 8-20"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.description, "Abarrotes y más")

    def test_validaciones(self):
        cliente = self.con_token("duena", "clave-segura-1")
        for dato in ({"color_principal": "verde"}, {"latitud": 200}, {"whatsapp": "abc"},
                     {"nombre": "El Vecino"}):
            r = cliente.patch("/api/mi-tienda/", dato, format="json")
            self.assertEqual(r.status_code, 400, dato)

    def test_slug_no_se_puede_cambiar(self):
        cliente = self.con_token("duena", "clave-segura-1")
        cliente.patch("/api/mi-tienda/", {"slug": "hack", "nombre": "Nuevo Nombre"}, format="json")
        self.tienda.refresh_from_db()
        self.assertEqual(self.tienda.slug, "la-esquina")
        self.assertEqual(self.tienda.name, "Nuevo Nombre")

    def test_cada_dueno_ve_su_tienda(self):
        r = self.con_token("vecino", "clave-segura-2").get("/api/mi-tienda/")
        self.assertEqual(r.json()["nombre"], "El Vecino")

    def test_logout_invalida_el_token(self):
        cliente = self.con_token("duena", "clave-segura-1")
        self.assertEqual(cliente.post("/api/auth/logout/").status_code, 204)
        self.assertEqual(cliente.get("/api/mi-tienda/").status_code, 401)

    def test_subir_logo(self):
        cliente = self.con_token("duena", "clave-segura-1")
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, "PNG")
        archivo = SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            r = cliente.patch("/api/mi-tienda/", {"logo": archivo}, format="multipart")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/media/tiendas/logos/", r.json()["logo"])