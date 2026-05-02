"""Multilingual i18n support.

Primitives for managing user-facing translations across the four
languages of the project's i18n contract:

- Spanish (``es``) — authoritative for every AEAT domain term
  (modelos, casillas, BOE references, legal terminology). Default
  output language for the CLI.
- English (``en``) — authoritative for code, docstrings, and
  developer-facing documentation.
- Catalan (``ca``) — co-official across Catalunya, Illes Balears,
  and the Comunitat Valenciana; required for any UX that targets
  Catalan-speaking autónomos. Tax terminology grounded in the
  Generalitat de Catalunya / Agència Tributària de Catalunya
  legal glossary.
- Hungarian (``hu``) — secondary operator language for the day-to-day
  user; provides a localised surface independent of the AEAT-facing
  Spanish strings.
"""

from __future__ import annotations

import re
import unicodedata
from enum import StrEnum
from typing import Any, Protocol, TypedDict, cast, runtime_checkable

from ..config import load_settings
from ..errors import AeatError

_LANGUAGE_CODE_PATTERN = re.compile(r"^[a-z]{2}$")

# Hardcoded last-resort fallback order. Spanish first so AEAT
# terminology stays legible when every other key is missing; English
# next as the developer-facing lingua franca; Catalan and Hungarian
# trail because both are optional under the authoritative-language
# matrix and may be unpopulated on freshly seeded records.
_HARDCODED_FALLBACK_ORDER: tuple[str, ...] = ("es", "en", "ca", "hu")


class TranslationError(AeatError):
    """Raised when a required translation is missing or invalid."""


class Language(StrEnum):
    """Multilingual contract languages.

    ISO 639-1 codes. Values are lowercase to match the storage shape
    used throughout the corpus and to round-trip cleanly through
    :func:`normalize_language_code`.
    """

    ES = "es"
    EN = "en"
    CA = "ca"
    HU = "hu"


class Translatable(TypedDict, total=False):
    """A translatable string carrier in the multilingual contract.

    Nested-dict shape, keyed by ISO 639-1 code:

    - ``es``: Authoritative for AEAT domain terms; the canonical
      legal text. Always present on any AEAT-derived record.
    - ``en``: Authoritative for code and technical documentation;
      the working language of the project.
    - ``ca``: Catalan rendering for UX that targets Catalan-speaking
      autónomos. Tax acronyms (IVA, IRPF) are kept identical to
      Spanish per Generalitat / ATC publication conventions.
    - ``hu``: Hungarian rendering for the operator's day-to-day CLI use.

    Every key is ``total=False`` so callers may seed records
    incrementally, but the authoritative key for the record's domain
    (``es`` for AEAT, ``en`` for project docs) is enforced by
    :func:`require_authoritative`.
    """

    es: str
    en: str
    ca: str
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


def normalize_language_code(language: str | Language) -> str:
    """Normalize and validate a language code against the multilingual contract."""

    value = language if isinstance(language, str) else language.value
    normalized = value.strip().lower()
    if not _LANGUAGE_CODE_PATTERN.fullmatch(normalized):
        raise TranslationError(f"Language must be a two-letter ISO 639-1 code, got {value!r}")
    return normalized


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
    fallback_chain = [lang.strip() for lang in settings.aeat_fallback_languages.split(",") if lang.strip()]

    for lang in fallback_chain:
        if lang in translatable and translatable.get(lang):  # type: ignore[misc]
            return _normalize_text(str(translatable.get(lang)))  # type: ignore[misc]

    # Final hardcoded fallback order as a last resort. Order is fixed
    # at module level (es, en, ca, hu) so behaviour stays deterministic
    # even when settings are unreadable.
    for lang_code in _HARDCODED_FALLBACK_ORDER:
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
