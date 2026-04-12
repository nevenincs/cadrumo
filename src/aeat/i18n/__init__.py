"""Trilingual i18n support.

Provides primitives for managing translations across Spanish (es),
English (en), and Hungarian (hu).
"""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Any, Protocol, TypedDict, cast, runtime_checkable

from aeat.config import load_settings
from aeat.errors import AeatError


class TranslationError(AeatError):
    """Raised when a required translation is missing or invalid."""


class Language(StrEnum):
    """Trilingual contract languages."""

    ES = "es"
    EN = "en"
    HU = "hu"


class Translatable(TypedDict, total=False):
    """A translatable string representation in the trilingual contract.

    Nested-dict shape:
    - es: Authoritative for AEAT domain terms.
    - en: Authoritative for code and technical docs.
    - hu: User-facing output.
    """

    es: str
    en: str
    hu: str


@runtime_checkable
class TranslatableObject(Protocol):
    """Interface for objects containing a 'translation' field."""

    translation: Translatable


class TranslationFallback(StrEnum):
    """Policies for translation fallback."""

    STRICT = "strict"
    FALLBACK_TO_EN = "fallback_to_en"
    FALLBACK_TO_ES = "fallback_to_es"
    CONFIG = "config"


def _normalize_text(text: str) -> str:
    """Apply NFC normalization to ensure consistent string representation."""
    return unicodedata.normalize("NFC", text)


def get_translation(
    translatable: Translatable,
    target_lang: Language,
    fallback_policy: TranslationFallback | None = None,
) -> str:
    """Retrieve the best available translation for the target language.

    Args:
        translatable: A Translatable dictionary.
        target_lang: The desired Language.
        fallback_policy: Optional fallback policy. If None, uses the
            AEAT_FALLBACK_LANGUAGES setting.

    Returns:
        The translated string (NFC normalized).

    Raises:
        TranslationError: If the target language is missing and no fallback
            is available or strict policy is enforced.
    """
    lang_val = target_lang.value

    if lang_val in translatable and translatable.get(lang_val):  # type: ignore[misc]
        return _normalize_text(str(translatable.get(lang_val)))  # type: ignore[misc]

    if fallback_policy == TranslationFallback.STRICT:
        raise TranslationError(f"Missing strictly required translation for {lang_val}")

    if fallback_policy == TranslationFallback.FALLBACK_TO_EN and translatable.get("en"):
        return _normalize_text(str(translatable["en"]))

    if fallback_policy == TranslationFallback.FALLBACK_TO_ES and translatable.get("es"):
        return _normalize_text(str(translatable["es"]))

    # Use configuration-defined fallbacks
    settings = load_settings()
    fallback_chain = [lang.strip() for lang in settings.aeat_fallback_languages.split(",")]

    for lang in fallback_chain:
        if lang in translatable and translatable.get(lang):  # type: ignore[misc]
            return _normalize_text(str(translatable.get(lang)))  # type: ignore[misc]

    # Final hardcoded fallbacks as a last resort
    for lang_code in ["en", "es", "hu"]:
        if translatable.get(lang_code):  # type: ignore[misc]
            return _normalize_text(str(translatable.get(lang_code)))  # type: ignore[misc]

    raise TranslationError("No translation available in any language")


def require_authoritative(translatable: Translatable, domain: str = "aeat") -> str:
    """Ensure the authoritative language for the domain is present.

    Args:
        translatable: A Translatable dictionary.
        domain: Context domain ('aeat' or 'docs').

    Returns:
        The authoritative translated string (NFC normalized).

    Raises:
        TranslationError: If the authoritative language is missing or domain is invalid.
    """
    if domain == "aeat":
        if not translatable.get("es"):
            raise TranslationError("Missing authoritative language 'es' for 'aeat' domain")
        return _normalize_text(str(translatable["es"]))
    elif domain == "docs":
        if not translatable.get("en"):
            raise TranslationError("Missing authoritative language 'en' for 'docs' domain")
        return _normalize_text(str(translatable["en"]))

    raise TranslationError(f"Unknown domain: {domain}")


def with_translation(obj: dict[str, Any], translatable: Translatable) -> dict[str, Any]:
    """Inject a Translatable dictionary into an object.

    Args:
        obj: The target dictionary.
        translatable: The Translatable to inject.

    Returns:
        A new dictionary with the translation merged.
    """
    # Normalize all translations before injecting
    normalized_translatable: Translatable = cast(
        Translatable,
        {k: _normalize_text(str(v)) for k, v in translatable.items()},
    )
    new_obj = dict(obj)
    new_obj["translation"] = normalized_translatable
    return new_obj
