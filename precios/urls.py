from django.urls import path

from . import views

urlpatterns = [
    path("categorias/", views.CategoriaListView.as_view()),
    path("tiendas/", views.TiendaListView.as_view()),
    path("tiendas/<slug:slug>/", views.TiendaDetalleView.as_view()),
    path("inicio/", views.InicioView.as_view()),
    path("comparador/", views.ComparadorView.as_view()),
]