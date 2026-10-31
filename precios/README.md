# Comparador de precios

Backend en Django + DRF. Cada tienda de barrio carga sus precios; el comparador los junta.

## Levantar el proyecto

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    python manage.py migrate
    python manage.py seed_demo
    python manage.py createsuperuser
    python manage.py runserver

- API: http://127.0.0.1:8000/api/
- Documentación (Swagger): http://127.0.0.1:8000/api/docs/
- Admin: http://127.0.0.1:8000/admin/
- Usuarios de tienda de ejemplo: demo_tienda1 ... demo_tienda6 (contraseña: demo1234)