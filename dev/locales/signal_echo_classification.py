"""Echo classification for the authoritative locale audit."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from difflib import SequenceMatcher
from importlib import import_module
from pathlib import Path

from cadrumo.core.toml import TomlDecodeError, load_toml

from .signal_syntax import (
    ARCHITECTURE_TOKEN_RE,
    MODELO_FORM_RE,
    PLATFORM_FORMAT_RE,
    PLATFORM_LABEL_RE,
    VERSION_TOKEN_RE,
)
from .signal_tokens import filtered_translation_text, translation_words


def product_identity_echo_reason(source: str, normalized: str) -> str | None:
    """Product identity echo reason."""
    from cadrumo.core.product_identity import PRODUCT_IDENTITY

    product_names = tuple(value for value in PRODUCT_IDENTITY if isinstance(value, str))
    normalized_product_names = {translation_echo_normalize(value) for value in product_names}
    if normalized in normalized_product_names or is_product_version_identity(source, product_names):
        return "canonical_product_identity"
    return None


def symbol_or_modelo_echo_reason(source: str) -> str | None:
    """Symbol or modelo echo reason."""
    glyphs = tuple(character for character in source if not character.isspace())
    if glyphs and all(unicodedata.category(character).startswith(("P", "S")) for character in glyphs):
        return "symbol_only"
    if MODELO_FORM_RE.search(source):
        return "modelo_form"
    return None


def platform_token_echo_reason(source: str) -> str | None:
    """Platform token echo reason."""
    words = translation_words(source)
    if words and all(word.isupper() or not word.isalpha() for word in words):
        return "platform_format"
    if PLATFORM_FORMAT_RE.search(source) and len(words) <= 2:
        return "platform_format"
    return None


def platform_identity_echo_reason(source: str, normalized: str, platform_terms: Iterable[str]) -> str | None:
    """Platform identity echo reason."""
    if PLATFORM_LABEL_RE.search(source) and any(
        ARCHITECTURE_TOKEN_RE.search(match.group("details")) for match in PLATFORM_LABEL_RE.finditer(source)
    ):
        return "platform_format"
    normalized_platform_terms = {translation_echo_normalize(term) for term in platform_terms}
    if normalized in normalized_platform_terms:
        return "platform_format"
    return None


def inline_code_echo_reason(source: str, filtered: str, excluded: int) -> str | None:
    """Inline code echo reason."""
    if (
        excluded
        and not any(character.isalpha() for character in filtered)
        and any(character.isalnum() for character in VERSION_TOKEN_RE.sub(" ", source))
    ):
        return "inline_code"
    return None


def shared_dictionary_echo_reason(
    locale: str, dictionary: object | None, source_dictionary: object | None, dictionary_words: tuple[str, ...]
) -> str | None:
    """Shared dictionary echo reason."""
    lookup = getattr(dictionary, "lookup", None)
    if locale != "en" and callable(lookup) and dictionary_words and all(lookup(word) for word in dictionary_words):
        source_is_valid = source_dictionary_accepts_words(source_dictionary, dictionary_words)
        # A single shared loanword/name (for example ``Manual``) is not
        # evidence of an untranslated sentence.  For multiple words, an
        # English-dictionary hit on every word wins over the target hit so a
        # genuine English phrase cannot be silenced by vocabulary overlap.
        if len(dictionary_words) == 1 or not source_is_valid:
            return "target_dictionary_shared_term"
    return None


def translation_echo_normalize(value: str) -> str:
    """Normalize a translation/source pair for semantic echo comparison."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = " ".join(normalized.split()).casefold()
    normalized = "".join(" " if unicodedata.category(char).startswith("P") else char for char in normalized)
    return " ".join(normalized.split())


def translation_similarity(left: str, right: str) -> float:
    """Return a normalized similarity ratio using rapidfuzz when installed."""
    try:
        fuzz = import_module("rapidfuzz.fuzz")
    except ImportError:
        return SequenceMatcher(None, left, right).ratio()
    ratio = getattr(fuzz, "ratio", None)
    if not callable(ratio):
        return SequenceMatcher(None, left, right).ratio()
    score = ratio(left, right)
    return score / 100 if isinstance(score, (int, float)) else SequenceMatcher(None, left, right).ratio()


def translation_invariant_echo_reason(
    source: str,
    locale: str,
    *,
    dictionary: object | None,
    source_dictionary: object | None = None,
    platform_terms: Iterable[str] = (),
) -> str | None:
    """Classify an exact echo only when its invariance is independently provable."""
    normalized = translation_echo_normalize(source)
    reason = product_identity_echo_reason(source, normalized)
    if reason is not None:
        return reason
    reason = symbol_or_modelo_echo_reason(source)
    if reason is not None:
        return reason
    reason = platform_token_echo_reason(source)
    if reason is not None:
        return reason
    reason = platform_identity_echo_reason(source, normalized, platform_terms)
    if reason is not None:
        return reason
    filtered, excluded = filtered_translation_text(source)
    reason = inline_code_echo_reason(source, filtered, excluded)
    if reason is not None:
        return reason
    dictionary_words = translation_words(filtered)
    reason = shared_dictionary_echo_reason(locale, dictionary, source_dictionary, dictionary_words)
    if reason is not None:
        return reason
    return None


def is_product_version_identity(source: str, product_names: Iterable[str]) -> bool:
    """Return whether *source* is only a canonical product name and version."""
    if VERSION_TOKEN_RE.search(source) is None:
        return False
    remainder = VERSION_TOKEN_RE.sub(" ", source)
    product_found = False
    for name in sorted(product_names, key=len, reverse=True):
        remainder, substitutions = re.subn(re.escape(name), " ", remainder, flags=re.IGNORECASE)
        product_found = product_found or substitutions > 0
    return product_found and not any(character.isalnum() for character in remainder)


def load_platform_identity_terms(repository: Path) -> frozenset[str]:
    """Load platform identity spellings from the canonical download descriptor."""
    descriptor = repository / "docs" / "_data" / "download_channels.toml"
    try:
        with descriptor.open("rb") as handle:
            payload = load_toml(handle)
    except (OSError, TomlDecodeError):
        return frozenset[str]()
    channels = payload.get("channel")
    if not isinstance(channels, list):
        return frozenset[str]()
    terms: set[str] = set()
    for channel in channels:
        if not isinstance(channel, dict):
            continue
        platform = channel.get("platform")
        if not isinstance(platform, str):
            continue
        for match in PLATFORM_LABEL_RE.finditer(platform):
            terms.add(translation_echo_normalize(match.group(0)))
            terms.add(translation_echo_normalize(match.group("label")))
    return frozenset(terms)


def source_dictionary_accepts_words(source_dictionary: object | None, dictionary_words: tuple[str, ...]) -> bool:
    """Source dictionary accepts words."""
    source_lookup = getattr(source_dictionary, "lookup", None)
    source_is_valid = callable(source_lookup) and all(source_lookup(word) for word in dictionary_words)
    return source_is_valid
