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
class PanelTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.duena = User.objects.create_user("duena2")        # sin contraseña: más rápido
        self.vecino = User.objects.create_user("vecino2")
        self.tienda = Store.objects.create(
            name="Mi Tienda", slug="mi-tienda", owner=self.duena, latitude=-17.39, longitude=-66.15)
        self.otra = Store.objects.create(
            name="Otra Tienda", slug="otra-tienda", owner=self.vecino, latitude=-17.40, longitude=-66.16)
        Category.objects.create(name="Lácteos", slug="lacteos")
        self.api = self.cliente(self.duena)
        self.api_vecino = self.cliente(self.vecino)

    def cliente(self, usuario):
        token, _ = Token.objects.get_or_create(user=usuario)
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Token " + token.key)
        return c

    def crear(self, cliente=None, **cambios):
        datos = {"nombre": "Leche entera", "marca": "PIL", "presentacion": "1 L", "precio": "9.50"}
        datos.update(cambios)
        return (cliente or self.api).post("/api/mi-tienda/productos/", datos, format="json")

    def test_exige_token(self):
        self.assertEqual(APIClient().get("/api/mi-tienda/productos/").status_code, 401)

    def test_crear_producto(self):
        r = self.crear(categoria="lacteos")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["nombre"], "Leche entera")
        self.assertEqual(r.json()["categoria"], "Lácteos")
        self.assertEqual(Price.objects.get(store=self.tienda).amount, Decimal("9.50"))

    def test_repetir_producto_actualiza_el_precio_sin_duplicar(self):
        self.crear()
        r = self.crear(nombre="LECHE entera", precio="8.00")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Price.objects.get(store=self.tienda).amount, Decimal("8.00"))

    def test_dos_tiendas_comparten_el_producto_y_el_comparador_las_junta(self):
        self.crear()
        self.crear(cliente=self.api_vecino, precio="8.80")
        self.assertEqual(Product.objects.count(), 1)
        item = self.client.get("/api/comparador/", {"q": "leche"}).json()["results"][0]
        self.assertEqual([p["tienda"]["slug"] for p in item["precios"]], ["otra-tienda", "mi-tienda"])

    def test_codigo_de_barras_reutiliza_producto(self):
        self.crear(nombre="Leche A", codigo_barras="7771234567890")
        self.crear(cliente=self.api_vecino, nombre="Leche B distinta", codigo_barras="7771234567890")
        self.assertEqual(Product.objects.count(), 1)

    def test_vincular_producto_existente_por_id(self):
        producto_id = self.crear().json()["producto_id"]
        r = self.api_vecino.post("/api/mi-tienda/productos/",
                                 {"producto_id": producto_id, "precio": "7.00"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Price.objects.filter(store=self.otra).count(), 1)

    def test_validaciones_de_producto(self):
        for datos in ({"precio": "0"}, {"precio": "-3"}, {"precio": "abc"},
                      {"categoria": "no-existe"}, {"codigo_barras": "12"}, {"producto_id": 9999}):
            self.assertEqual(self.crear(**datos).status_code, 400, datos)
        r = self.api.post("/api/mi-tienda/productos/", {"precio": "5"}, format="json")
        self.assertEqual(r.status_code, 400)       # sin nombre ni producto_id

    def test_subir_imagen(self):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "blue").save(buffer, "PNG")
        archivo = SimpleUploadedFile("leche.png", buffer.getvalue(), content_type="image/png")
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            r = self.api.post("/api/mi-tienda/productos/",
                              {"nombre": "Leche", "precio": "9", "imagen": archivo}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertIn("/media/precios/", r.json()["imagen"])

    def test_listar_solo_mis_productos_y_buscar_con_error_de_tipeo(self):
        self.crear()
        self.crear(nombre="Arroz", marca="", presentacion="1 kg", precio="9")
        self.crear(cliente=self.api_vecino, nombre="Papa", precio="5")
        self.assertEqual(self.api.get("/api/mi-tienda/productos/").json()["count"], 2)
        r = self.api.get("/api/mi-tienda/productos/", {"q": "lehce"}).json()
        self.assertEqual([p["nombre"] for p in r["results"]], ["Leche entera"])

    def test_editar_precio_y_disponibilidad(self):
        precio_id = self.crear().json()["id"]
        r = self.api.patch(f"/api/mi-tienda/productos/{precio_id}/",
                           {"precio": "10.00", "disponible": False}, format="json")
        self.assertEqual(r.status_code, 200)
        precio = Price.objects.get(pk=precio_id)
        self.assertEqual(precio.amount, Decimal("10.00"))
        self.assertFalse(precio.available)

    def test_no_se_puede_tocar_el_precio_de_otra_tienda(self):
        precio_id = self.crear().json()["id"]
        url = f"/api/mi-tienda/productos/{precio_id}/"
        self.assertEqual(self.api_vecino.patch(url, {"precio": "1"}, format="json").status_code, 404)
        self.assertEqual(self.api_vecino.delete(url).status_code, 404)
        self.assertEqual(Price.objects.get(pk=precio_id).amount, Decimal("9.50"))

    def test_borrar_quita_el_precio_pero_no_el_producto(self):
        precio_id = self.crear().json()["id"]
        self.assertEqual(self.api.delete(f"/api/mi-tienda/productos/{precio_id}/").status_code, 204)
        self.assertEqual(Price.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 1)

    def test_sugerencias(self):
        self.crear()
        r = self.api_vecino.get("/api/mi-tienda/productos/sugerencias/", {"q": "lec"}).json()
        self.assertEqual(r[0]["nombre"], "Leche entera")

    def test_crear_promocion_y_verla_en_el_inicio(self):
        producto_id = self.crear().json()["producto_id"]
        r = self.api.post("/api/mi-tienda/promociones/",
                          {"titulo": "Oferta leche", "producto": producto_id, "precio_promo": "8.00"},
                          format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.api.get("/api/mi-tienda/promociones/").json()["count"], 1)
        promo = self.client.get("/api/inicio/").json()["promociones_destacadas"][0]
        self.assertEqual(promo["precio_mas_bajo"]["precio"], 8.0)

    def test_reglas_de_promocion(self):
        producto_id = self.crear().json()["producto_id"]       # lo vendo a 9.50
        malas = [
            {"titulo": "x", "producto": producto_id, "precio_promo": "9.50"},    # no es menor
            {"titulo": "x", "producto": 99999},                                   # no lo vendo
            {"titulo": "x", "valida_desde": "2026-12-10", "valida_hasta": "2026-12-01"},
            {"descripcion": "sin título"},
        ]
        for datos in malas:
            r = self.api.post("/api/mi-tienda/promociones/", datos, format="json")
            self.assertEqual(r.status_code, 400, datos)

    def test_promocion_ajena_es_404(self):
        promo_id = self.api.post("/api/mi-tienda/promociones/", {"titulo": "General"},
                                 format="json").json()["id"]
        url = f"/api/mi-tienda/promociones/{promo_id}/"
        self.assertEqual(self.api_vecino.delete(url).status_code, 404)
        self.assertEqual(self.api.delete(url).status_code, 204)

import csv
from openpyxl import Workbook, load_workbook


class ImportTests(TestCase):
    def setUp(self):
        User = get_user_model()
        owner = User.objects.create_user("duena3")
        self.store = Store.objects.create(
            name="Tienda Excel", slug="tienda-excel", owner=owner,
            latitude=-17.39, longitude=-66.15,
        )
        Category.objects.create(name="Lácteos", slug="lacteos")
        token, _ = Token.objects.get_or_create(user=owner)
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def archivo(self, rows):
        book = Workbook()
        sheet = book.active
        for row in rows:
            sheet.append(row)
        buffer = io.BytesIO()
        book.save(buffer)
        buffer.seek(0)
        return SimpleUploadedFile(
            "productos.xlsx", buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_descarga_la_plantilla(self):
        response = self.api.get("/api/mi-tienda/plantilla/")
        self.assertEqual(response.status_code, 200)
        book = load_workbook(io.BytesIO(response.content))
        self.assertEqual(book.active["A1"].value, "nombre")

    def test_importa_y_actualiza_sin_duplicar(self):
        rows = [
            ["nombre", "marca", "presentacion", "categoria", "precio", "codigo_barras", "disponible"],
            ["Leche entera", "PIL", "1 L", "lacteos", 9.5, "7771234567890", "si"],
        ]
        first = self.api.post("/api/mi-tienda/importar/", {"archivo": self.archivo(rows)}, format="multipart")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["creados"], 1)

        rows[1][4] = 8.4
        second = self.api.post("/api/mi-tienda/importar/", {"archivo": self.archivo(rows)}, format="multipart")
        self.assertEqual(second.json()["actualizados"], 1)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Price.objects.get(store=self.store).amount, Decimal("8.40"))

    def test_una_fila_mala_no_frena_a_las_buenas(self):
        rows = [
            ["nombre", "precio", "categoria"],
            ["Arroz", 9, "lacteos"],
            ["", -1, "no-existe"],
            ["Fideo", 6.5, ""],
        ]
        report = self.api.post(
            "/api/mi-tienda/importar/", {"archivo": self.archivo(rows)}, format="multipart",
        ).json()
        self.assertEqual(report["creados"], 2)
        self.assertEqual(report["errores"][0]["fila"], 3)
        self.assertIn("nombre", report["errores"][0]["errores"])
        self.assertIn("precio", report["errores"][0]["errores"])
        self.assertIn("categoria", report["errores"][0]["errores"])

    def test_rechaza_otro_formato_y_pide_token(self):
        bad = SimpleUploadedFile("notas.txt", b"hola", content_type="text/plain")
        self.assertEqual(
            self.api.post("/api/mi-tienda/importar/", {"archivo": bad}, format="multipart").status_code,
            400,
        )
        self.assertEqual(APIClient().get("/api/mi-tienda/plantilla/").status_code, 401)