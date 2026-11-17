from django.urls import path

from . import views

urlpatterns = [
    path("categorias/", views.CategoriaListView.as_view()),
    path("tiendas/", views.TiendaListView.as_view()),
    path("tiendas/<slug:slug>/", views.TiendaDetalleView.as_view()),
    path("tiendas/<slug:slug>/productos/", views.TiendaProductosView.as_view()),
    path("reservas/", views.ReservaCrearView.as_view()),
    path("reservas/mias/", views.ReservasConsultaView.as_view()),
    path("inicio/", views.InicioView.as_view()),
    path("comparador/", views.ComparadorView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("mi-tienda/", views.MiTiendaView.as_view()),
    path("mi-tienda/productos/", views.MisProductosView.as_view()),
    path("mi-tienda/productos/sugerencias/", views.SugerenciasProductoView.as_view()),
    path("mi-tienda/productos/<int:pk>/", views.MiProductoDetalleView.as_view()),
    path("mi-tienda/promociones/", views.MisPromocionesView.as_view()),
    path("mi-tienda/promociones/<int:pk>/", views.MiPromocionDetalleView.as_view()),
    path("mi-tienda/plantilla/", views.PlantillaView.as_view()),
    path("mi-tienda/importar/", views.ImportarView.as_view()),
]