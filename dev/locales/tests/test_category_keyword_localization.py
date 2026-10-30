"""Localized desktop category keywords retain Spanish search aliases."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

from .._paths import LOCALES_DIR
from ..signal_translation_matrix import suspicious_translation_locales

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_LOCALIZED_KEYWORDS = {
    ("ca", "arrendamiento_local"): {"lloguer", "negoci", "arrendament"},
    ("ca", "arrendamiento_vivienda_afecto"): {"lloguer", "habitatge", "pis"},
    ("ca", "gastos_bancarios"): {"comissió", "bancària", "transferència"},
    ("ca", "software_suscripcion"): {"programari", "subscripció", "llicència"},
    ("ca", "vehiculo_combustible"): {"benzina", "dièsel", "cotxe"},
    ("en", "arrendamiento_local"): {"rent", "premises", "lease"},
    ("en", "arrendamiento_vivienda_afecto"): {"rent", "home", "flat", "lease"},
    ("hu", "arrendamiento_local"): {"üzlethelyiség", "iroda", "bérleti", "bérlemény"},
    ("hu", "arrendamiento_vivienda_afecto"): {"lakás", "otthon", "albérlet", "bérleti"},
    ("hu", "gastos_bancarios"): {"banki", "jutalék", "bankszámla", "átutalás"},
    ("hu", "software_suscripcion"): {"szoftver", "előfizetés", "licenc", "alkalmazás"},
}


@cache
def _category_keywords(locale: str) -> dict[str, str]:
    """Read the authoritative category-keyword section from a locale shard."""
    source = Path(LOCALES_DIR) / locale / "common.yml"
    document: Any = yaml.safe_load(source.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    for part in ("desktop", "ledger", "category_keywords"):
        document = document.get(part)
        assert isinstance(document, dict), f"missing {part!r} in {source}"
    keywords: dict[str, str] = {}
    for key, value in document.items():
        assert isinstance(key, str)
        assert isinstance(value, str)
        keywords[key] = value
    return keywords


@pytest.mark.parametrize(
    ("locale", "key", "localized_terms"),
    tuple((locale, key, terms) for (locale, key), terms in _LOCALIZED_KEYWORDS.items()),
)
def test_category_keywords_keep_spanish_terms_and_add_locale_terms(
    locale: str,
    key: str,
    localized_terms: set[str],
) -> None:
    """Search works with both Spanish source documents and the interface locale."""
    spanish = _category_keywords("es")[key]
    translated = _category_keywords(locale)[key]
    dotted_key = f"desktop.ledger.category_keywords.{key}"
    locale_leaves = {code: {dotted_key: _category_keywords(code)[key]} for code in ("es", "en", "ca", "hu")}

    assert set(spanish.split()) <= set(translated.split())
    assert localized_terms <= set(translated.split())
    assert locale not in suspicious_translation_locales(dotted_key, locale_leaves)
