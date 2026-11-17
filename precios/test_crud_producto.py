import io
import os
import tempfile
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Category, Price, Product, Promotion, Store


class PanelBase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.duena = User.objects.create_user("duena2")
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


class CrudProductoUnicoTests(PanelBase):
    """Crear/editar/borrar UN producto desde el panel."""

    def url(self, precio_id):
        return f"/api/mi-tienda/productos/{precio_id}/"

    def test_detalle_indica_si_el_catalogo_es_editable(self):
        item = self.crear(categoria="lacteos").json()
        self.assertTrue(item["catalogo_editable"])
        self.assertEqual(item["categoria_slug"], "lacteos")
        self.crear(cliente=self.api_vecino)                  # otra tienda lo vende también
        self.assertFalse(self.api.get(self.url(item["id"])).json()["catalogo_editable"])

    def test_corregir_nombre_marca_categoria_y_codigo_si_solo_yo_lo_vendo(self):
        pid = self.crear(nombre="Lehce", marca="Pil").json()["id"]
        r = self.api.patch(self.url(pid), {"nombre": "Leche", "marca": "PIL", "categoria": "lacteos",
                                           "codigo_barras": "7771234567890", "precio": "11"},
                           format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.json()["nombre"], "Leche")
        self.assertEqual(r.json()["categoria"], "Lácteos")
        self.assertEqual(r.json()["precio"], 11.0)
        found = self.client.get("/api/comparador/", {"q": "leche"}).json()["results"]
        self.assertEqual(len(found), 1)

    def test_quitar_la_categoria(self):
        pid = self.crear(categoria="lacteos").json()["id"]
        r = self.api.patch(self.url(pid), {"categoria": ""}, format="json")
        self.assertIsNone(r.json()["categoria"])

    def test_no_se_pueden_cambiar_datos_del_catalogo_si_otra_tienda_lo_vende(self):
        pid = self.crear().json()["id"]
        self.crear(cliente=self.api_vecino)
        r = self.api.patch(self.url(pid), {"nombre": "Otra cosa"}, format="json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(Product.objects.get().name, "Leche entera")
        r = self.api.patch(self.url(pid), {"precio": "7", "nombre": "Leche entera"}, format="json")
        self.assertEqual(r.status_code, 200)

    def test_renombrar_a_un_producto_que_ya_existe_da_400_con_su_id(self):
        self.crear(cliente=self.api_vecino, nombre="Arroz", marca="", presentacion="1 kg")
        pid = self.crear(nombre="Arros", marca="", presentacion="1 kg").json()["id"]
        r = self.api.patch(self.url(pid), {"nombre": "ARROZ"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("producto_id", r.json()["nombre"][0])

    def test_codigo_de_barras_repetido_en_edicion_da_400(self):
        self.crear(cliente=self.api_vecino, nombre="Otro", codigo_barras="7771234567890")
        pid = self.crear().json()["id"]
        r = self.api.patch(self.url(pid), {"codigo_barras": "7771234567890"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("codigo_barras", r.json())

    def test_edicion_es_todo_o_nada(self):
        pid = self.crear().json()["id"]
        self.crear(cliente=self.api_vecino, nombre="Arroz", marca="", presentacion="1 kg")
        r = self.api.patch(self.url(pid), {"precio": "1.50", "nombre": "Arroz", "marca": "",
                                           "presentacion": "1 kg"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Price.objects.get(pk=pid).amount, Decimal("9.50"))

    def test_validaciones_de_edicion(self):
        pid = self.crear().json()["id"]
        for datos in ({"precio": "0"}, {"nombre": "  "}, {"codigo_barras": "12"},
                      {"categoria": "no-existe"}, {"precio": "abc"}):
            self.assertEqual(self.api.patch(self.url(pid), datos, format="json").status_code, 400, datos)

    def test_no_se_puede_subir_el_precio_por_encima_de_mi_promocion(self):
        r = self.crear()
        self.api.post("/api/mi-tienda/promociones/",
                      {"titulo": "Oferta", "producto": r.json()["producto_id"], "precio_promo": "9.00"},
                      format="json")
        bad = self.api.patch(self.url(r.json()["id"]), {"precio": "8.50"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("precio", bad.json())
        ok = self.api.patch(self.url(r.json()["id"]), {"precio": "12"}, format="json")
        self.assertEqual(ok.status_code, 200)

    def _png(self, nombre="a.png"):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, "PNG")
        return SimpleUploadedFile(nombre, buffer.getvalue(), content_type="image/png")

    def test_reemplazar_y_quitar_imagen_borra_el_archivo_viejo(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(MEDIA_ROOT=tmp):
            pid = self.crear().json()["id"]
            self.api.patch(self.url(pid), {"imagen": self._png("uno.png")}, format="multipart")
            primero = Price.objects.get(pk=pid).image.path
            self.assertTrue(os.path.exists(primero))
            self.api.patch(self.url(pid), {"imagen": self._png("dos.png")}, format="multipart")
            self.assertFalse(os.path.exists(primero))
            segundo = Price.objects.get(pk=pid).image.path
            self.assertTrue(os.path.exists(segundo))
            r = self.api.patch(self.url(pid), {"imagen": ""}, format="multipart")
            self.assertEqual(r.status_code, 200, r.content)
            self.assertIsNone(r.json()["imagen"])
            self.assertFalse(os.path.exists(segundo))

    def test_mandar_otros_campos_en_multipart_no_cambia_disponible(self):
        pid = self.crear(disponible=False).json()["id"]
        self.api.patch(self.url(pid), {"precio": "5"}, format="multipart")
        self.assertFalse(Price.objects.get(pk=pid).available)

    def test_borrar_con_otras_tiendas_conserva_el_producto_y_borra_mis_promociones(self):
        r = self.crear()
        self.crear(cliente=self.api_vecino)
        self.api.post("/api/mi-tienda/promociones/",
                      {"titulo": "Mia", "producto": r.json()["producto_id"], "precio_promo": "8"},
                      format="json")
        self.api_vecino.post("/api/mi-tienda/promociones/",
                             {"titulo": "Suya", "producto": r.json()["producto_id"], "precio_promo": "8"},
                             format="json")
        self.assertEqual(self.api.delete(self.url(r.json()["id"])).status_code, 204)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Promotion.objects.filter(store=self.tienda).count(), 0)
        self.assertEqual(Promotion.objects.filter(store=self.otra).count(), 1)

    def test_filtros_y_orden_de_la_lista(self):
        self.crear(nombre="Arroz", marca="", presentacion="1 kg", precio="9")
        self.crear(nombre="Azúcar", marca="", presentacion="1 kg", precio="6", disponible=False)
        self.crear(nombre="Fideo", marca="", presentacion="400 g", precio="4")
        nombres = lambda **p: [x["nombre"] for x in
                               self.api.get("/api/mi-tienda/productos/", p).json()["results"]]
        self.assertEqual(nombres(), ["Arroz", "Azúcar", "Fideo"])
        self.assertEqual(nombres(orden="precio"), ["Fideo", "Azúcar", "Arroz"])
        self.assertEqual(nombres(orden="-precio"), ["Arroz", "Azúcar", "Fideo"])
        self.assertEqual(nombres(disponible="0"), ["Azúcar"])
        self.assertEqual(nombres(disponible="1", orden="precio"), ["Fideo", "Arroz"])