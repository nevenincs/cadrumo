"""Production runtime helpers for :mod:`aeat.filing`.

The filing runtime must not depend on :mod:`aeat.filing.testing`.
This module exposes the concrete profile and schema-provider
implementations used by the CLI and workflow surfaces, backed by the
same in-tree filing schemas the builders execute against today.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..deadlines import AutonomoProfile, applies_to
from ._builders._modelo_130_schema import (
    MODELO_130_SCHEMA,
    CasillaSource,
    StaticCasillaCollection,
    StaticCasillaSchema,
    StaticCasillaSchemaProvider,
)
from ._builders._modelo_303_schema import MODELO_303_SCHEMA
from ._builders._modelo_390_schema import MODELO_390_SCHEMA

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_SUPPORTED_FILING_MODELOS: tuple[str, ...] = ("130", "303", "390")

RuntimeCasillaSchema = StaticCasillaSchema
RuntimeCasillaCollection = StaticCasillaCollection
RuntimeCasillaSchemaProvider = StaticCasillaSchemaProvider


class FilingOperatorProfile(BaseModel):
    """Concrete runtime implementation of the filing-profile Protocol."""

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    applicable_modelos: tuple[str, ...] = Field(default_factory=tuple)


def filing_profile_from_autonomo(
    profile: AutonomoProfile,
    *,
    display_name: str | None = None,
) -> FilingOperatorProfile:
    """Project an :class:`AutonomoProfile` into the filing profile Protocol."""
    applicable = tuple(modelo for modelo in _SUPPORTED_FILING_MODELOS if applies_to(profile, modelo))
    return FilingOperatorProfile(
        tax_id=profile.tax_id,
        display_name=(display_name or profile.tax_id).strip(),
        applicable_modelos=applicable,
    )


def load_default_filing_profile(
    path: Path | None = None,
    *,
    display_name: str | None = None,
) -> FilingOperatorProfile:
    """Load the configured default profile JSON for runtime filing commands."""
    from ..config import load_settings

    settings = load_settings()
    target = path or settings.aeat_default_profile_path
    if target is None:
        raise ValueError("no default filing profile configured; pass --profile PATH or set AEAT_DEFAULT_PROFILE_PATH")
    if not target.exists():
        raise ValueError(f"default filing profile not found: {target}")
    from ..setup._env_writer import load_profile_envelope

    profile = load_profile_envelope(target)
    return filing_profile_from_autonomo(profile, display_name=display_name)


def build_runtime_schema_provider() -> RuntimeCasillaSchemaProvider:
    """Return the production filing schema provider.

    The provider is backed by the current filing-engine collections for
    modelos 130/303/390. This keeps the runtime on the exact schema the
    builders and validator understand today, while avoiding any import
    dependency on the test-only helper module.
    """

    return RuntimeCasillaSchemaProvider(
        collections={
            "130": _clone_collection(MODELO_130_SCHEMA),
            "303": _clone_collection(MODELO_303_SCHEMA),
            "390": _clone_collection(MODELO_390_SCHEMA),
        }
    )


def _clone_collection(collection: StaticCasillaCollection) -> RuntimeCasillaCollection:
    return RuntimeCasillaCollection(
        schema_version=collection.schema_version,
        casillas=tuple(
            RuntimeCasillaSchema(
                id=casilla.id,
                value_type=casilla.value_type,
                required=casilla.required,
                formula_inputs=casilla.formula_inputs,
                min_value=casilla.min_value,
                max_value=casilla.max_value,
                default=casilla.default,
                description=casilla.description,
                sources=casilla.sources,
                valid_from=casilla.valid_from,
                valid_to=casilla.valid_to,
            )
            for casilla in collection.casillas
        ),
    )


__all__ = [
    "CasillaSource",
    "FilingOperatorProfile",
    "RuntimeCasillaCollection",
    "RuntimeCasillaSchema",
    "RuntimeCasillaSchemaProvider",
    "build_runtime_schema_provider",
    "filing_profile_from_autonomo",
    "load_default_filing_profile",
]
