"""Trilingual i18n support.

Provides primitives for managing translations across Spanish (es),
English (en), and Hungarian (hu).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, TypedDict

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


class TranslationFallback(StrEnum):
    """Policies for translation fallback."""

    STRICT = "strict"
    FALLBACK_TO_EN = "fallback_to_en"
    FALLBACK_TO_ES = "fallback_to_es"


def get_translation(
    translatable: Translatable,
    target_lang: Language,
    fallback_policy: TranslationFallback | None = None,
) -> str:
    """Retrieve the best available translation for the target language.

    Args:
        translatable: A Translatable dictionary.
        target_lang: The desired Language.
        fallback_policy: Optional fallback policy.

    Returns:
        The translated string.

    Raises:
        TranslationError: If the target language is missing and no fallback
            is available or strict policy is enforced.
    """
    lang_val = target_lang.value

    if lang_val in translatable and translatable.get(lang_val):  # type: ignore[misc]
        return str(translatable.get(lang_val))  # type: ignore[misc]

    if fallback_policy == TranslationFallback.STRICT:
        raise TranslationError(f"Missing strictly required translation for {lang_val}")

    if fallback_policy == TranslationFallback.FALLBACK_TO_EN and translatable.get("en"):
        return str(translatable["en"])

    if fallback_policy == TranslationFallback.FALLBACK_TO_ES and translatable.get("es"):
        return str(translatable["es"])

    # Default fallbacks if no specific policy or policy match fails
    if translatable.get("en"):
        return str(translatable["en"])
    if translatable.get("es"):
        return str(translatable["es"])
    if translatable.get("hu"):
        return str(translatable["hu"])

    raise TranslationError("No translation available in any language")


def require_authoritative(translatable: Translatable, domain: str = "aeat") -> str:
    """Ensure the authoritative language for the domain is present.

    Args:
        translatable: A Translatable dictionary.
        domain: Context domain ('aeat' or 'docs').

    Returns:
        The authoritative translated string.

    Raises:
        TranslationError: If the authoritative language is missing or domain is invalid.
    """
    if domain == "aeat":
        if not translatable.get("es"):
            raise TranslationError("Missing authoritative language 'es' for 'aeat' domain")
        return str(translatable["es"])
    elif domain == "docs":
        if not translatable.get("en"):
            raise TranslationError("Missing authoritative language 'en' for 'docs' domain")
        return str(translatable["en"])

    raise TranslationError(f"Unknown domain: {domain}")


def with_translation(obj: dict[str, Any], translatable: Translatable) -> dict[str, Any]:
    """Inject a Translatable dictionary into an object.

    Args:
        obj: The target dictionary.
        translatable: The Translatable to inject.

    Returns:
        A new dictionary with the translation merged.
    """
    new_obj = dict(obj)
    new_obj["translation"] = translatable
    return new_obj
