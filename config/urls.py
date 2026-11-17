from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


urlpatterns = [
    path(
        "",
        TemplateView.as_view(template_name="precios/inicio.html"),
        name="inicio",
    ),
    path(
        "acceso/",
        TemplateView.as_view(template_name="precios/login.html"),
        name="acceso",
    ),
    path(
        "panel/",
        TemplateView.as_view(template_name="precios/panel.html"),
        name="panel",
    ),
    path("admin/", admin.site.urls),
    path("api/", include("precios.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view            (url_name="schema"), name="docs"),
        path(
        "tiendas/<slug:slug>/",
        TemplateView.as_view(template_name="precios/tienda.html"),
        name="tienda",
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)