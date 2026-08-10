"""Canonical locale-key identity and scalar resolution for Modelo schemas."""

from __future__ import annotations

import base64
import re
from typing import Final, Literal

from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n import MissingTranslationError, lookup_translation

ModeloLocalizationField = Literal["label", "help", "title", "official_name"]

_PLAIN_SEGMENT: Final = re.compile(r"^[A-Za-z0-9_-]+$")
_ENCODED_PREFIX: Final[str] = "x-"
_SOURCE_LOCALE: Final[str] = "es"
_MODEL_SCOPED_CONSTRUCTS: Final[frozenset[tuple[str, str]]] = frozenset({("303", "modelo-303-iva-autoliquidacion")})


def encode_modelo_locale_segment(value: str) -> str:
    """Encode one dynamic identity as an injective dotted-key segment."""
    if _PLAIN_SEGMENT.fullmatch(value) and not value.startswith(_ENCODED_PREFIX):
        return value
    encoded = base64.b32hexencode(value.encode(UTF_8_ENCODING)).decode("ascii").rstrip("=").lower()
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


def construct_locale_key(
    modelo_id: str,
    revision_id: str,
    construct_id: str,
    field: Literal["title"] = "title",
) -> str:
    """Derive the presentation key for one construct at its declared ownership scope."""
    if (modelo_id, construct_id) in _MODEL_SCOPED_CONSTRUCTS:
        return (
            f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.construct."
            f"{encode_modelo_locale_segment(construct_id)}.field.{field}"
        )
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.revision."
        f"{encode_modelo_locale_segment(revision_id)}.construct."
        f"{encode_modelo_locale_segment(construct_id)}.field.{field}"
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


def casilla_alias_locale_key(
    modelo_id: str,
    revision_id: str,
    casilla_id: str,
    alias_id: str,
    field: Literal["label"] = "label",
) -> str:
    """Derive the presentation key for one casilla alias occurrence."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.revision."
        f"{encode_modelo_locale_segment(revision_id)}.casilla."
        f"{encode_modelo_locale_segment(casilla_id)}.alias."
        f"{encode_modelo_locale_segment(alias_id)}.{field}"
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

    Resolution advances on the absence of a VALUE, never on the absence of a
    key.  That distinction is the whole reason the less-specific tiers can
    fire: the locale scaffold emits an occurrence key for every casilla in
    every revision, null until translated, and exempts those nulls from the
    untranslated-string honesty ratchet.  So the first key in the chain always
    exists.  A chain that stopped at key EXISTENCE therefore stopped at index
    zero every time, for every casilla in every revision, and the continuity
    tier below it was written, scaffolded and never once consulted.

    The stop it used to perform was meant to let a revision deliberately blank
    an inherited label, but the catalogue cannot express that intent: an
    explicit null and a scaffolded-but-untranslated null are the same bytes, so
    the stop could only ever suppress translations nobody chose to suppress.
    Restoring the override needs a way to say "blanked on purpose" in the data,
    not a stop that fires on every untranslated key.

    This is invisible in Spanish, which is why it survived: the Spanish
    backstop lives in the OUTER loop, so every casilla carrying Spanish text
    resolved correctly no matter what the inner loop did.  Only a casilla
    lacking a value in the requested locale ever reached the tier that was
    broken.
    """
    for candidate_locale in (locale, _SOURCE_LOCALE) if locale != _SOURCE_LOCALE else (_SOURCE_LOCALE,):
        for key in keys:
            value = lookup_translation(key, locale=candidate_locale)
            if value is not None:
                return value.format(year=year) if year is not None and "{year}" in value else value
    if required:
        raise MissingTranslationError(key=keys[0], locale=_SOURCE_LOCALE)
    return None


__all__ = [
    "ModeloLocalizationField",
    "casilla_alias_locale_key",
    "casilla_continuity_locale_key",
    "casilla_occurrence_locale_key",
    "construct_locale_key",
    "encode_modelo_locale_segment",
    "modelo_locale_key",
    "resolve_modelo_localization",
    "revision_locale_key",
]
