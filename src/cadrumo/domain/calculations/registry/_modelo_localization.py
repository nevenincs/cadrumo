"""Canonical locale-key identity and scalar resolution for Modelo schemas."""

from __future__ import annotations

import base64
import re
from typing import Final, Literal

from ....core.i18n import MissingTranslationError, lookup_translation_entry

ModeloLocalizationField = Literal["label", "help", "title", "official_name"]

_PLAIN_SEGMENT: Final = re.compile(r"^[A-Za-z0-9_-]+$")
_ENCODED_PREFIX: Final[str] = "x-"
_SOURCE_LOCALE: Final[str] = "es"


def encode_modelo_locale_segment(value: str) -> str:
    """Encode one dynamic identity as an injective dotted-key segment."""
    if _PLAIN_SEGMENT.fullmatch(value) and not value.startswith(_ENCODED_PREFIX):
        return value
    encoded = base64.b32hexencode(value.encode("utf-8")).decode("ascii").rstrip("=").lower()
    return f"{_ENCODED_PREFIX}{encoded}"


def modelo_locale_key(modelo_id: str, field: Literal["title", "official_name"]) -> str:
    """Derive a Modelo-level presentation key."""
    return f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.field.{field}"


def revision_locale_key(modelo_id: str, revision_id: str, field: Literal["label"] = "label") -> str:
    """Derive a revision-level presentation key."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.revision."
        f"{encode_modelo_locale_segment(revision_id)}.field.{field}"
    )


def casilla_occurrence_locale_key(
    modelo_id: str,
    revision_id: str,
    casilla_id: str,
    field: Literal["label", "help"],
) -> str:
    """Derive the exact revision-occurrence key for one casilla field."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.revision."
        f"{encode_modelo_locale_segment(revision_id)}.casilla."
        f"{encode_modelo_locale_segment(casilla_id)}.{field}"
    )


def casilla_continuity_locale_key(
    modelo_id: str,
    continuidad_id: str,
    field: Literal["label", "help"],
) -> str:
    """Derive the stable continuity key for one grounded casilla field."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.casilla.continuidad."
        f"{encode_modelo_locale_segment(continuidad_id)}.{field}"
    )


def resolve_modelo_localization(
    keys: tuple[str, ...],
    *,
    locale: str,
    required: bool,
    year: int | None = None,
) -> str | None:
    """Resolve exact/variant keys, then continuity, with Spanish fallback.

    ``keys`` is ordered from most-specific to least-specific.  The requested
    locale is exhausted before the same identity chain is resolved through the
    mandatory Spanish source.  No non-Spanish locale can become another
    non-Spanish locale's fallback.
    """
    for candidate_locale in (locale, _SOURCE_LOCALE) if locale != _SOURCE_LOCALE else (_SOURCE_LOCALE,):
        for key in keys:
            present, value = lookup_translation_entry(key, locale=candidate_locale)
            if value is not None:
                return value.format(year=year) if year is not None and "{year}" in value else value
            if present:
                break
    if required:
        raise MissingTranslationError(key=keys[0], locale=_SOURCE_LOCALE)
    return None


__all__ = [
    "ModeloLocalizationField",
    "casilla_continuity_locale_key",
    "casilla_occurrence_locale_key",
    "encode_modelo_locale_segment",
    "modelo_locale_key",
    "resolve_modelo_localization",
    "revision_locale_key",
]
