"""Schema-backed registry of editable taxpayer-profile keys.

The v6 CLI redesign mandates a schema-backed profile editor — the
operator must be able to discover editable keys, set / unset values,
and validate completeness without bespoke per-command knowledge. The
registry lives in the domain layer so every consumer (CLI, future
TUI, programmatic clients) reads from the same source of truth.

The registry is a tuple of strict :class:`ProfileKey` records. Each
entry carries the canonical key path (dot-separated), a requirement
flag (required vs optional for declaration export), and a short
multilingual description rendered in operator-facing surfaces.

Adding a new key means appending a :class:`ProfileKey` row here and
extending the validators that consume the value. Adding a new
language means extending :class:`aeat.core.i18n.Language`; the
description fields fall back through
:func:`aeat.core.i18n.require_authoritative` when a per-language
slot is empty.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ...core.i18n import Translatable, TranslationError, require_authoritative


class ProfileKeyRequirement(StrEnum):
    """Whether a profile key is mandatory before declaration export."""

    REQUIRED = "required"
    OPTIONAL = "optional"


class ProfileKey(BaseModel):
    """Strict frozen record describing one editable profile key."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=128)
    requirement: ProfileKeyRequirement
    description: Translatable

    @field_validator("key")
    @classmethod
    def _validate_key_shape(cls, value: str) -> str:
        """Reject blank or whitespace-padded keys; keep dot-separated paths intact."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("key must not be empty or whitespace-only")
        if trimmed != value:
            raise ValueError("key must not be padded with whitespace")
        return trimmed

    @field_validator("description")
    @classmethod
    def _require_authoritative_description(cls, value: Translatable) -> Translatable:
        """Reject descriptions without an authoritative Spanish rendering."""
        try:
            require_authoritative(value, domain="aeat")
        except TranslationError as exc:
            raise ValueError(str(exc)) from exc
        return value


def _key(
    *,
    key: str,
    requirement: ProfileKeyRequirement,
    es: str,
    en: str,
    ca: str,
    hu: str,
) -> ProfileKey:
    """Construct a :class:`ProfileKey` with a multilingual description."""
    return ProfileKey(
        key=key,
        requirement=requirement,
        description={"es": es, "en": en, "ca": ca, "hu": hu},
    )


PROFILE_KEYS: tuple[ProfileKey, ...] = (
    _key(
        key="tax.id",
        requirement=ProfileKeyRequirement.REQUIRED,
        es="Identificador fiscal usado en los borradores locales de declaración.",
        en="Tax identifier used for local declaration drafts.",
        ca="Identificador fiscal utilitzat en els esborranys locals de declaració.",
        hu="Helyi bevallás-tervezetekhez használt adóazonosító.",
    ),
    _key(
        key="name",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Nombre visible usado en la salida de revisión local.",
        en="Display name used in local review output.",
        ca="Nom visible utilitzat a la sortida de revisió local.",
        hu="A helyi áttekintés kimeneten megjelenő név.",
    ),
    _key(
        key="activity",
        requirement=ProfileKeyRequirement.REQUIRED,
        es="Etiqueta de actividad económica o clave de actividad controlada.",
        en="Business activity label or controlled activity key.",
        ca="Etiqueta d'activitat econòmica o clau d'activitat controlada.",
        hu="Gazdasági tevékenység címke vagy ellenőrzött tevékenységkulcs.",
    ),
    _key(
        key="address.postcode",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Código postal del domicilio fiscal cuando un Modelo soportado lo requiere.",
        en="Tax address postcode when a supported Modelo needs it.",
        ca="Codi postal del domicili fiscal quan un Modelo suportat el necessita.",
        hu="Adózási cím irányítószáma, ha valamely támogatott Modelo igényli.",
    ),
    _key(
        key="declaration.type",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Tipo de declaración para las cabeceras de exportación; por defecto I.",
        en="Declaration type for export headers; defaults to I.",
        ca="Tipus de declaració per a les capçaleres d'exportació; per defecte I.",
        hu="Bevallás-típus az exportfejlécekhez; alapértelmezett: I.",
    ),
)
"""Closed registry of editable taxpayer-profile keys.

Mirrors the v6 CLI redesign packet's "Candidate Profile Keys"
section. The CLI implementation team consumes this tuple directly
rather than maintaining a parallel hardcoded list.
"""


_BY_KEY: dict[str, ProfileKey] = {entry.key: entry for entry in PROFILE_KEYS}


def get_profile_key(key: str) -> ProfileKey:
    """Return the :class:`ProfileKey` for ``key``.

    Raises:
        KeyError: When ``key`` is not in the registry.
    """
    try:
        return _BY_KEY[key]
    except KeyError as exc:
        raise KeyError(f"unknown profile key: {key!r}") from exc


def required_profile_keys() -> tuple[ProfileKey, ...]:
    """Return only the keys whose :attr:`requirement` is ``REQUIRED``."""
    return tuple(entry for entry in PROFILE_KEYS if entry.requirement is ProfileKeyRequirement.REQUIRED)


def optional_profile_keys() -> tuple[ProfileKey, ...]:
    """Return only the keys whose :attr:`requirement` is ``OPTIONAL``."""
    return tuple(entry for entry in PROFILE_KEYS if entry.requirement is ProfileKeyRequirement.OPTIONAL)


__all__ = [
    "PROFILE_KEYS",
    "ProfileKey",
    "ProfileKeyRequirement",
    "get_profile_key",
    "optional_profile_keys",
    "required_profile_keys",
]
