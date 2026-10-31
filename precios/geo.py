from math import asin, cos, radians, sin, sqrt

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1, lon1, lat2, lon2):
    """Distancia en km en línea recta entre dos coordenadas."""
    phi1, phi2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(a))


def parse_coordinates(lat, lng):
    """Convierte lat/lng (texto que llega por la URL) en números válidos.
    Devuelve (lat, lng) o None si son inválidos."""
    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return None
    return lat, lng


def stores_by_distance(stores, lat, lng):
    """Lista de (tienda, km) de la más cercana a la más lejana."""
    result = [(s, haversine_km(lat, lng, s.latitude, s.longitude)) for s in stores]
    return sorted(result, key=lambda pair: pair[1])


def directions_url(store, origin_lat=None, origin_lng=None, mode="driving"):
    """Enlace que abre la ruta en Google Maps (no requiere clave de API)."""
    url = (
        "https://www.google.com/maps/dir/?api=1"
        f"&destination={store.latitude},{store.longitude}&travelmode={mode}"
    )
    if origin_lat is not None and origin_lng is not None:
        url += f"&origin={origin_lat},{origin_lng}"
    return url