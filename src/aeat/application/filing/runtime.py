"""Production runtime helpers for :mod:`aeat.application.filing`.

Exposes concrete profile helpers used by the CLI and workflow surfaces.
The production schema provider requires validated registry snapshots.

The filing runtime must not depend on
:mod:`aeat.application.filing.testing`; this module is the production
entry point that callers (CLI, workflow, services) construct profiles
and schema providers through.

Key entry points:

* :class:`FilingOperatorProfile` — pydantic v2 record satisfying the
  filing-profile Protocol.
* :func:`filing_profile_from_autonomo` — projects taxpayer identity from a
  domain :class:`aeat.domain.deadlines.AutonomoProfile` into the runtime
  profile shape without deriving legal filing obligations.
* :func:`load_default_filing_profile` — loads the configured default
  profile JSON and returns a runtime profile.
* :func:`build_runtime_schema_provider` — requires registry-backed snapshots.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ...core.paths import PROJECT_ROOT
from ...domain.calculations.registry import (
    CasillaDefinition,
    FormulaDefinition,
    ModeloDefinition,
    RegistryValidator,
    expression_casilla_refs,
    load_registry_tree,
)
from ...domain.filing import CasillaCollection, CasillaSchema, CasillaSchemaProvider
from ...domain.filing._errors import FilingBuilderError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class AutonomoProfileIdentity(Protocol):
    """Structural identity surface accepted by the filing profile projector."""

    @property
    def tax_id(self) -> str:
        """Tax identity copied into the filing runtime profile."""
        ...


class FilingOperatorProfile(BaseModel):
    """Concrete runtime implementation of the filing-profile Protocol.

    Strict, frozen pydantic v2 model satisfying the filing layer's
    profile Protocol.

    Attributes:
        tax_id: NIF / NIE of the filing operator.
        display_name: Human-readable label for the profile.
        applicable_modelos: Tuple of modelo codes supplied by a validated
            registry snapshot or an explicit caller boundary.
    """

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    applicable_modelos: tuple[str, ...] = Field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class RegistryCasillaSchema:
    """Filing schema projection for one registry casilla."""

    id: str
    value_type: str
    required: bool
    formula_inputs: tuple[str, ...]
    min_value: float | int | None = None
    max_value: float | int | None = None
    default: object | None = None


@dataclass(frozen=True, slots=True)
class RegistryCasillaCollection:
    """Filing schema collection projected from one modelo registry definition."""

    casillas: tuple[RegistryCasillaSchema, ...]
    schema_version: str

    def __iter__(self) -> object:
        return iter(self.casillas)

    def get(self, casilla_id: str) -> CasillaSchema | None:
        for casilla in self.casillas:
            if casilla.id == casilla_id:
                return casilla
        return None

    def all(self) -> Sequence[CasillaSchema]:
        return self.casillas


@dataclass(frozen=True, slots=True)
class RegistrySchemaProvider:
    """Registry-backed filing schema provider."""

    collections: dict[str, RegistryCasillaCollection]

    def get_collection(self, modelo: str) -> CasillaCollection:
        try:
            return self.collections[modelo]
        except KeyError as exc:
            raise FilingBuilderError(f"modelo {modelo!r} is not present in the calculation registry") from exc


def filing_profile_from_autonomo(
    profile: AutonomoProfileIdentity,
    *,
    display_name: str | None = None,
) -> FilingOperatorProfile:
    """Project an :class:`AutonomoProfile` into a :class:`FilingOperatorProfile`.

    This helper deliberately copies only taxpayer identity. Modelo
    applicability is legal filing truth and must come from validated
    registry data, not a filing-runtime tuple or the deadline engine.

    Args:
        profile: Source domain profile.
        display_name: Optional friendly label; defaults to
            ``profile.tax_id``.

    Returns:
        A frozen :class:`FilingOperatorProfile`.
    """
    return FilingOperatorProfile(
        tax_id=profile.tax_id,
        display_name=(display_name or profile.tax_id).strip(),
        applicable_modelos=(),
    )


def load_default_filing_profile(
    path: Path | None = None,
    *,
    display_name: str | None = None,
) -> FilingOperatorProfile:
    """Load the configured default profile JSON for runtime filing commands.

    Resolves ``path`` (or, when ``None``, the
    ``aeat_default_profile_path`` setting from
    :func:`aeat.core.config.load_settings`), validates the on-disk
    envelope via :func:`aeat.application.setup._env_writer.load_profile_envelope`,
    and projects it into a runtime :class:`FilingOperatorProfile`.

    Args:
        path: Override path to the profile JSON. Defaults to the
            value of ``AEAT_DEFAULT_PROFILE_PATH``.
        display_name: Optional friendly label propagated to the
            returned profile.

    Returns:
        The loaded :class:`FilingOperatorProfile`.

    Raises:
        FilingBuilderError: When no default profile is configured or when the
            resolved path does not exist on disk.
    """
    from ...core.config import load_settings

    settings = load_settings()
    target = path or settings.aeat_default_profile_path
    if target is None:
        raise FilingBuilderError(
            "no default filing profile configured; pass --profile PATH or set AEAT_DEFAULT_PROFILE_PATH"
        )
    if not target.exists():
        raise FilingBuilderError(f"default filing profile not found: {target}")
    from ..setup._env_writer import load_profile_envelope

    profile = load_profile_envelope(target)
    return filing_profile_from_autonomo(profile, display_name=display_name)


def build_runtime_schema_provider(
    registry_root: Path | None = None,
    *,
    source_root: Path | None = None,
) -> CasillaSchemaProvider:
    """Build the production schema provider from validated registry TOML."""

    root = registry_root or PROJECT_ROOT / "registry" / "aeat"
    resolved_source_root = source_root or PROJECT_ROOT
    modelos, catalogues = load_registry_tree(root)
    if not modelos:
        raise FilingBuilderError(f"registry root has no modelo definitions: {root}")
    validator = RegistryValidator(catalogues, source_root=resolved_source_root)
    return RegistrySchemaProvider(
        collections={modelo.id: _collection_from_modelo(modelo, validator) for modelo in modelos}
    )


def _collection_from_modelo(
    modelo: ModeloDefinition,
    validator: RegistryValidator,
) -> RegistryCasillaCollection:
    validator.validate_modelo(modelo)
    revision_ids = tuple(sorted(modelo.revisions))
    casillas: dict[str, RegistryCasillaSchema] = {}
    for revision in modelo.revisions.values():
        formulas = {formula.id: formula for formula in revision.formulas}
        for casilla in revision.casillas:
            existing = casillas.get(casilla.id)
            schema = _casilla_schema(casilla, formulas)
            if existing is not None and existing != schema:
                raise FilingBuilderError(f"modelo {modelo.id!r} has divergent schema for casilla {casilla.id!r}")
            casillas[casilla.id] = schema
    return RegistryCasillaCollection(
        casillas=tuple(casillas[key] for key in sorted(casillas)),
        schema_version=f"registry:{modelo.id}:{','.join(revision_ids)}",
    )


def _casilla_schema(
    casilla: CasillaDefinition,
    formulas: dict[str, FormulaDefinition],
) -> RegistryCasillaSchema:
    formula_inputs: tuple[str, ...] = ()
    if casilla.formula is not None:
        formula = formulas[casilla.formula]
        formula_inputs = tuple(dict.fromkeys(expression_casilla_refs(formula.expression)))
    return RegistryCasillaSchema(
        id=casilla.id,
        value_type=_value_type(casilla.data_type),
        required=casilla.required,
        formula_inputs=formula_inputs,
    )


def _value_type(data_type: str) -> str:
    if data_type in {"decimal", "money", "ratio"}:
        return "decimal"
    if data_type == "integer":
        return "int"
    if data_type == "text":
        return "str"
    if data_type == "boolean":
        return "bool"
    raise FilingBuilderError(f"unsupported registry casilla data type {data_type!r}")


__all__ = [
    "FilingOperatorProfile",
    "RegistryCasillaCollection",
    "RegistryCasillaSchema",
    "RegistrySchemaProvider",
    "build_runtime_schema_provider",
    "filing_profile_from_autonomo",
    "load_default_filing_profile",
]
