"""Small text helpers used for topic filtering."""
from __future__ import annotations

import unicodedata
from typing import Iterable


def normalize(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace ("Décès" -> "deces")."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.casefold().split())


def matches_topic(text: str, keywords: Iterable[str]) -> bool:
    """True if at least one keyword appears in the text (accent/case insensitive)."""
    haystack = normalize(text)
    return any(normalize(k) in haystack for k in keywords if k and k.strip())
