from rapidfuzz import fuzz

from .models import Synonym
from .texto import normalize, tokenize

FUZZY_MIN = 80          # similitud mínima (0-100) para aceptar un error de tipeo
SYNONYM_FACTOR = 0.85   # un sinónimo vale un poco menos que la palabra exacta


def token_match(token, words):
    """Compara UNA palabra de la consulta con las palabras del producto.
    Devuelve (puntaje, tipo)."""
    if token in words:
        return 100, "exacta"
    best = 0
    for w in words:
        if len(token) >= 3 and w.startswith(token):
            return 92, "exacta"
        best = max(best, fuzz.ratio(token, w))
    return (best, "similar") if best >= FUZZY_MIN else (0, "")


def phrase_match(tokens, words):
    """Todas las palabras de la consulta deben encontrarse."""
    results = [token_match(t, words) for t in tokens]
    if not results or any(score == 0 for score, _ in results):
        return 0, ""
    score = sum(s for s, _ in results) / len(results)
    kind = "exacta" if all(k == "exacta" for _, k in results) else "similar"
    return score, kind


def expand_query(query):
    """Devuelve la consulta normalizada y sus sinónimos."""
    q = normalize(query)
    q_words = set(tokenize(q))
    related = set()
    for terms in Synonym.objects.values_list("terms", flat=True):
        group = [normalize(t) for t in terms.split(",") if t.strip()]
        if q in group or any(t in q_words for t in group):
            related.update(t for t in group if t != q)
    return q, sorted(related)


def score_product(search_text, q, related):
    words = set(search_text.split())
    best = phrase_match(tokenize(q), words)
    for phrase in related:
        score, _ = phrase_match(tokenize(phrase), words)
        if score * SYNONYM_FACTOR > best[0]:
            best = (score * SYNONYM_FACTOR, "sinonimo")
    return best


def search_products(queryset, query, limit=40):
    """Devuelve [(producto, tipo, puntaje)] ordenado de mejor a peor."""
    q, related = expand_query(query)
    results = []
    for product in queryset:
        score, kind = score_product(product.search_text, q, related)
        if score:
            results.append((product, kind, round(score)))
    results.sort(key=lambda r: (-r[2], r[0].name))
    return results[:limit]