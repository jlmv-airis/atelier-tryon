"""Deteccion de categoria de prenda: upper_body | lower_body | dresses (logica pura + clasificador opcional)."""
from typing import Callable

CATEGORIES = ("upper_body", "lower_body", "dresses")

KEYWORDS = {
    "dresses": ("vestido", "dress", "gown", "jumpsuit", "mono", "enterizo", "overol", "romper"),
    "lower_body": ("pantalon", "pantalón", "jeans", "mezclilla", "falda", "skirt", "short", "leggin",
                   "trousers", "pants", "bermuda", "jogger"),
    "upper_body": ("blusa", "camisa", "camiseta", "playera", "top", "sueter", "suéter", "sweater", "hoodie",
                   "sudadera", "chaqueta", "jacket", "abrigo", "coat", "blazer", "shirt", "tee", "polo", "crop"),
}

ClassifyFn = Callable[[], str | None]


def normalize(value: str | None) -> str | None:
    value = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"upper": "upper_body", "top": "upper_body", "lower": "lower_body", "bottom": "lower_body",
               "dress": "dresses", "vestido": "dresses", "arriba": "upper_body", "abajo": "lower_body"}
    value = aliases.get(value, value)
    return value if value in CATEGORIES else None


def from_description(description: str) -> str | None:
    text = (description or "").lower()
    for category in ("dresses", "lower_body", "upper_body"):   # el vestido gana si aparece
        if any(word in text for word in KEYWORDS[category]):
            return category
    return None


def detect(requested: str | None, description: str, classify: ClassifyFn | None = None) -> str:
    """Prioridad: categoria pedida por el usuario > palabras clave > clasificador (vision) > upper_body."""
    explicit = normalize(requested)
    if explicit:
        return explicit
    guessed = from_description(description)
    if guessed:
        return guessed
    if classify is not None:
        try:
            predicted = normalize(classify())
            if predicted:
                return predicted
        except Exception:
            pass
    return "upper_body"
