"""Canonical locale-key identity and scalar resolution for Modelo schemas."""

from __future__ import annotations

import base64
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Final, Literal, cast

from ....core.external_constants import UTF_8_ENCODING
from ....core.i18n import MissingTranslationError, lookup_translation
from ....core.modelo import Modelo
from ....core.type_adapters import OBJECT_TUPLE_ADAPTER
from ._toml_helpers import as_toml_table as _as_toml_table
from .ids import RevisionId


class ModeloLocalizationFieldKind(StrEnum):
    """Which localizable text a modelo locale key addresses."""

    LABEL = "label"
    HELP = "help"
    TITLE = "title"
    OFFICIAL_NAME = "official_name"


ModeloLocalizationField = Literal[
    ModeloLocalizationFieldKind.LABEL,
    ModeloLocalizationFieldKind.HELP,
    ModeloLocalizationFieldKind.TITLE,
    ModeloLocalizationFieldKind.OFFICIAL_NAME,
]
"""Every localizable field."""

CasillaLocalizationField = Literal[
    ModeloLocalizationFieldKind.LABEL,
    ModeloLocalizationFieldKind.HELP,
]
"""The fields a CASILLA carries, which are only its label and its help text.

A narrowing written out twice before this existed. A casilla has no title and no
official name -- those belong to the modelo and its revision -- so keeping this narrow
stops a caller asking for a casilla key that can never resolve."""

_PLAIN_SEGMENT: Final = re.compile(r"^[A-Za-z0-9_-]+$")
_ENCODED_PREFIX: Final[str] = "x-"
_SOURCE_LOCALE: Final[str] = "es"
_MODEL_SCOPED_CONSTRUCTS: Final[frozenset[tuple[str, str]]] = frozenset(
    {(Modelo.M303.value, "modelo-303-iva-autoliquidacion")},
)


def encode_modelo_locale_segment(value: str) -> str:
    """Encode one dynamic identity as an injective dotted-key segment."""
    if _PLAIN_SEGMENT.fullmatch(value) and not value.startswith(_ENCODED_PREFIX):
        return value
    encoded = base64.b32hexencode(value.encode(UTF_8_ENCODING)).decode("ascii").rstrip("=").lower()
    return f"{_ENCODED_PREFIX}{encoded}"


def modelo_locale_key(modelo_id: str, field: Literal["title", "official_name"]) -> str:
    """Derive a Modelo-level presentation key."""
    return f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.field.{field}"


def revision_locale_key(
    modelo_id: str,
    revision_id: RevisionId,
    field: Literal[ModeloLocalizationFieldKind.LABEL] = ModeloLocalizationFieldKind.LABEL,
) -> str:
    """Derive a revision-level presentation key."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.revision."
        f"{encode_modelo_locale_segment(revision_id)}.field.{field}"
    )


def construct_locale_key(
    modelo_id: str,
    revision_id: RevisionId,
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
    revision_id: RevisionId,
    casilla_id: str,
    field: CasillaLocalizationField,
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
    field: CasillaLocalizationField,
) -> str:
    """Derive the stable continuity key for one grounded casilla field."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.casilla.continuidad."
        f"{encode_modelo_locale_segment(continuidad_id)}.{field}"
    )


def casilla_alias_locale_key(
    modelo_id: str,
    revision_id: RevisionId,
    casilla_id: str,
    alias_id: str,
    field: Literal[ModeloLocalizationFieldKind.LABEL] = ModeloLocalizationFieldKind.LABEL,
) -> str:
    """Derive the presentation key for one casilla alias occurrence."""
    return (
        f"modelo.schema.{encode_modelo_locale_segment(modelo_id)}.revision."
        f"{encode_modelo_locale_segment(revision_id)}.casilla."
        f"{encode_modelo_locale_segment(casilla_id)}.alias."
        f"{encode_modelo_locale_segment(alias_id)}.{field}"
    )


def _passthrough_localization_row(raw: object) -> dict[str, object]:
    """Carry malformed locale-owned rows through to the schema validator."""
    if isinstance(raw, Mapping):
        return dict(cast(Mapping[str, object], raw))
    return {"value": raw}


def _localised_casilla_aliases(
    raw_aliases: object,
    *,
    modelo_id: str,
    revision_id: RevisionId,
    casilla_id: str,
) -> tuple[dict[str, object], ...] | None:
    """Return one casilla's aliases with derived locale keys, or ``None`` if absent."""
    aliases_array = as_toml_array(raw_aliases)
    if aliases_array is None:
        return None
    aliases: list[dict[str, object]] = []
    for alias_index, raw_alias in enumerate(aliases_array):
        alias = _as_toml_table(raw_alias)
        if alias is None:
            aliases.append(_passthrough_localization_row(raw_alias))
            continue
        aliases.append(
            {
                **alias,
                "localization_key": casilla_alias_locale_key(
                    modelo_id,
                    revision_id,
                    casilla_id,
                    str(alias_index),
                ),
            },
        )
    return tuple(aliases)


def _localised_casilla(raw_casilla: object, *, modelo_id: str, revision_id: RevisionId) -> dict[str, object]:
    """Return one casilla with its derived locale keys attached."""
    casilla = _as_toml_table(raw_casilla)
    if casilla is None:
        return _passthrough_localization_row(raw_casilla)
    casilla_id = casilla.get("id")
    if not isinstance(casilla_id, str):
        return dict(casilla)
    keys = [casilla_occurrence_locale_key(modelo_id, revision_id, casilla_id, ModeloLocalizationFieldKind.LABEL)]
    continuidad_id = casilla.get("continuidad_id")
    if isinstance(continuidad_id, str):
        keys.append(casilla_continuity_locale_key(modelo_id, continuidad_id, ModeloLocalizationFieldKind.LABEL))
    payload: dict[str, object] = {**casilla, "localization_keys": tuple(keys)}
    aliases = _localised_casilla_aliases(
        casilla.get("aliases"),
        modelo_id=modelo_id,
        revision_id=revision_id,
        casilla_id=casilla_id,
    )
    if aliases is not None:
        payload["aliases"] = aliases
    return payload


def _localised_construct(raw_construct: object, *, modelo_id: str, revision_id: RevisionId) -> dict[str, object]:
    """Return one construct with its derived locale key attached."""
    construct = _as_toml_table(raw_construct)
    if construct is None:
        return _passthrough_localization_row(raw_construct)
    construct_id = construct.get("id")
    if not isinstance(construct_id, str):
        return dict(construct)
    return {
        **construct,
        "localization_key": construct_locale_key(modelo_id, revision_id, construct_id),
    }


def as_toml_array(value: object) -> tuple[object, ...] | None:
    """Narrow a frozen TOML array to object entries, or return ``None``."""
    if not isinstance(value, tuple):
        return None
    return OBJECT_TUPLE_ADAPTER.validate_python(value)


def enroll_revision_localization(
    *,
    modelo_id: str,
    revision_id: RevisionId,
    raw_revision: Mapping[str, object],
) -> dict[str, object]:
    """Attach derived locale identities without copying presentation values."""
    payload: dict[str, object] = {
        "id": revision_id,
        **raw_revision,
        "localization_key": revision_locale_key(modelo_id, revision_id),
    }
    raw_casillas = as_toml_array(raw_revision.get("casillas"))
    if raw_casillas is not None:
        payload["casillas"] = tuple(
            _localised_casilla(raw_casilla, modelo_id=modelo_id, revision_id=revision_id)
            for raw_casilla in raw_casillas
        )
    raw_constructs = as_toml_array(raw_revision.get("constructs"))
    if raw_constructs is not None:
        payload["constructs"] = tuple(
            _localised_construct(raw_construct, modelo_id=modelo_id, revision_id=revision_id)
            for raw_construct in raw_constructs
        )
    return payload


def resolve_modelo_localization(
    keys: tuple[str, ...],
    *,
    locale: str,
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
    return None


def require_modelo_localization(
    keys: tuple[str, ...],
    *,
    locale: str,
    year: int | None = None,
) -> str:
    """Resolve a label that must exist, refusing an untranslated identity chain.

    The same resolution order as :func:`resolve_modelo_localization`; the
    difference is the contract on absence. A construct title, official modelo
    name, or revision member label has no honest empty rendering, so an
    unresolved chain is a :class:`MissingTranslationError` rather than ``None``
    for the caller to interpret.
    """
    resolved = resolve_modelo_localization(keys, locale=locale, year=year)
    if resolved is None:
        raise MissingTranslationError(key=keys[0], locale=_SOURCE_LOCALE)
    return resolved


__all__ = [
    "CasillaLocalizationField",
    "ModeloLocalizationField",
    "ModeloLocalizationFieldKind",
    "casilla_alias_locale_key",
    "casilla_continuity_locale_key",
    "casilla_occurrence_locale_key",
    "construct_locale_key",
    "encode_modelo_locale_segment",
    "modelo_locale_key",
    "require_modelo_localization",
    "resolve_modelo_localization",
    "revision_locale_key",
]
