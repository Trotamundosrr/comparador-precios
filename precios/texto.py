import re
import unicodedata

STOPWORDS = {"de", "del", "la", "el", "los", "las", "en", "con", "para", "y", "a"}


def normalize(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def tokenize(text):
    """Palabras útiles de un texto, sin 'de', 'la', etc."""
    return [t for t in normalize(text).split() if t not in STOPWORDS]