"""Schema-backed registry of editable taxpayer-profile keys.

The operator can discover editable keys, set or unset values, and
validate completeness without bespoke per-command knowledge. The
registry lives in the domain layer so every consumer reads from the
same source of truth.

The registry is a tuple of strict :class:`ProfileKey` records. Each
entry carries the canonical key path (dot-separated), a requirement
flag (required vs optional for declaration export), and a short
multilingual description rendered in operator-facing surfaces.

Adding a new key means appending a :class:`ProfileKey` row here and
extending the validators that consume the value. Adding a new
language means extending :class:`aeat.core.i18n.str`; the
description fields fall back through
:func:`aeat.core.i18n.require_authoritative` when a per-language
slot is empty.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ...core.i18n import Translatable as tr  # noqa: N813


class ProfileKeyRequirement(StrEnum):
    """Whether a profile key is mandatory before declaration export."""

    REQUIRED = "required"
    OPTIONAL = "optional"


class ProfileKey(BaseModel):
    """Strict frozen record describing one editable profile key."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    key: str = Field(min_length=1, max_length=128)
    requirement: ProfileKeyRequirement
    description: tr
    required_when_key: str | None = None
    required_when_value: str | None = None

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
    def _validate_description_key(cls, value: tr) -> tr:
        """Require profile-owned translation keys for authoritative descriptions."""
        if not value.strip():
            raise ValueError("description must not be empty")
        if not str(value).startswith("profile."):
            raise ValueError("description must use a profile translation key")
        return value

    @field_validator("required_when_key", "required_when_value")
    @classmethod
    def _validate_conditional_requirement(cls, value: str | None) -> str | None:
        if value is not None and value.strip() != value:
            raise ValueError("conditional requirement fields must not be padded")
        if value == "":
            raise ValueError("conditional requirement fields must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_conditional_requirement_pair(self) -> ProfileKey:
        has_key = self.required_when_key is not None
        has_value = self.required_when_value is not None
        if has_key != has_value:
            raise ValueError("required_when_key and required_when_value must be set together")
        return self


def _key(
    *,
    key: str,
    requirement: ProfileKeyRequirement,
    es: str,
    en: str,
    ca: str,
    hu: str,
    required_when_key: str | None = None,
    required_when_value: str | None = None,
) -> ProfileKey:
    """Construct a :class:`ProfileKey` with a multilingual description."""
    return ProfileKey(
        key=key,
        requirement=requirement,
        description=tr(f"profile.key.{key}"),
        required_when_key=required_when_key,
        required_when_value=required_when_value,
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
        key="surnames",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Apellidos o razón social usados en las cabeceras de exportación.",
        en="Surnames or company name used in export headers.",
        ca="Cognoms o raó social utilitzats a les capçaleres d'exportació.",
        hu="Az exportfejlécekben használt vezetéknév vagy cégnév.",
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
        es="Tipo de declaración para las cabeceras de exportación.",
        en="Declaration type for export headers.",
        ca="Tipus de declaració per a les capçaleres d'exportació.",
        hu="Bevallás-típus az exportfejlécekhez.",
    ),
    _key(
        key="taxpayer.sex",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Sexo del primer declarante según el diseño oficial del Modelo 100.",
        en="First taxpayer sex according to the official Modelo 100 design.",
        ca="Sexe del primer declarant segons el disseny oficial del Modelo 100.",
        hu="Az első adózó neme a hivatalos Modelo 100 szerkezet szerint.",
    ),
    _key(
        key="taxpayer.marital_status",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Estado civil del primer declarante a 31 de diciembre del ejercicio.",
        en="First taxpayer marital status on 31 December of the tax year.",
        ca="Estat civil del primer declarant a 31 de desembre de l'exercici.",
        hu="Az első adózó családi állapota az adóév december 31-én.",
    ),
    _key(
        key="taxpayer.birth_date",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Fecha de nacimiento del primer declarante para Modelo 100.",
        en="First taxpayer birth date for Modelo 100.",
        ca="Data de naixement del primer declarant per al Modelo 100.",
        hu="Az első adózó születési dátuma a Modelo 100-hoz.",
    ),
    _key(
        key="spouse.tax.id",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="NIF/NIE del cónyuge cuando la declaración conjunta lo requiere.",
        en="Spouse NIF/NIE when joint taxation requires it.",
        ca="NIF/NIE del cònjuge quan la declaració conjunta ho requereix.",
        hu="A házastárs NIF/NIE azonosítója, ha a közös bevallás megköveteli.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.name",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Nombre del cónyuge para los datos identificativos de Modelo 100.",
        en="Spouse given name for Modelo 100 identity data.",
        ca="Nom del cònjuge per a les dades identificatives del Modelo 100.",
        hu="A házastárs keresztneve a Modelo 100 azonosító adataihoz.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.surnames",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Apellidos del cónyuge para los datos identificativos de Modelo 100.",
        en="Spouse surnames for Modelo 100 identity data.",
        ca="Cognoms del cònjuge per a les dades identificatives del Modelo 100.",
        hu="A házastárs vezetéknevei a Modelo 100 azonosító adataihoz.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.birth_date",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Fecha de nacimiento del cónyuge para Modelo 100.",
        en="Spouse birth date for Modelo 100.",
        ca="Data de naixement del cònjuge per al Modelo 100.",
        hu="A házastárs születési dátuma a Modelo 100-hoz.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
    _key(
        key="spouse.sex",
        requirement=ProfileKeyRequirement.OPTIONAL,
        es="Sexo del cónyuge según el diseño oficial del Modelo 100.",
        en="Spouse sex according to the official Modelo 100 design.",
        ca="Sexe del cònjuge segons el disseny oficial del Modelo 100.",
        hu="A házastárs neme a hivatalos Modelo 100 szerkezet szerint.",
        required_when_key="declaration.type",
        required_when_value="2",
    ),
)
"""Closed registry of editable taxpayer-profile keys."""


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
