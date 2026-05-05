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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ...core.paths import PROJECT_ROOT
from ...domain.calculations.registry import (
    CasillaDefinition,
    ExportLayoutDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistryCatalogues,
    RegistrySnapshot,
    RegistryValidator,
    build_snapshot,
    expression_casilla_refs,
    load_registry_tree,
)
from ...domain.filing import CasillaCollection, CasillaSchema
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
    """

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


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
class RegistryFilingSubview:
    """Snapshot-backed filing details for one modelo revision."""

    modelo_id: str
    revision_id: str
    schema_version: str
    cadence: str
    period_selector_periods: tuple[str, ...]
    legal_ref_ids: tuple[str, ...]
    source_ref_ids: tuple[str, ...]
    extraction_profile_ids: tuple[str, ...]
    verification_expectation_ids: tuple[str, ...]
    reconciliation_total_casillas: Mapping[str, str]
    export_layout_ids: tuple[str, ...]
    export_layouts: tuple[ExportLayoutDefinition, ...]
    application_link_ids: tuple[str, ...]
    deadline_window_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RegistrySchemaProvider:
    """Registry-backed filing schema provider."""

    collections: dict[str, RegistryCasillaCollection]
    subviews: dict[str, RegistryFilingSubview]

    def get_collection(self, modelo: str) -> CasillaCollection:
        try:
            return self.collections[modelo]
        except KeyError as exc:
            raise FilingBuilderError(f"modelo {modelo!r} is not present in the calculation registry") from exc

    def get_subview(self, modelo: str) -> RegistryFilingSubview:
        """Return the validated registry subview backing ``modelo``."""

        try:
            return self.subviews[modelo]
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
    filing_year: int | None = None,
    period: str | None = None,
) -> RegistrySchemaProvider:
    """Build the production schema provider from validated registry TOML."""

    root = registry_root or PROJECT_ROOT / "registry" / "aeat"
    resolved_source_root = source_root or PROJECT_ROOT
    modelos, catalogues = load_registry_tree(root)
    if not modelos:
        raise FilingBuilderError(f"registry root has no modelo definitions: {root}")
    validator = RegistryValidator(catalogues, source_root=resolved_source_root)
    snapshots = {
        modelo.id: _snapshot_for_provider(
            modelo,
            catalogues,
            source_root=resolved_source_root,
            filing_year=filing_year,
            period=period,
        )
        for modelo in modelos
    }
    return RegistrySchemaProvider(
        collections={
            modelo_id: _collection_from_snapshot(snapshot, validator) for modelo_id, snapshot in snapshots.items()
        },
        subviews={modelo_id: _subview_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
    )


def _snapshot_for_provider(
    modelo: ModeloDefinition,
    catalogues: RegistryCatalogues,
    *,
    source_root: Path,
    filing_year: int | None,
    period: str | None,
) -> RegistrySnapshot:
    if (filing_year is None) != (period is None):
        raise FilingBuilderError("filing_year and period must be supplied together")
    if filing_year is not None and period is not None:
        return build_snapshot(
            modelo,
            catalogues,
            source_root=source_root,
            filing_year=filing_year,
            period=period,
        )
    revision = _current_provider_revision(modelo)
    selector = revision.period_selector
    provider_year = selector.years[0] if selector.years else selector.year_from
    if provider_year is None:
        raise FilingBuilderError(f"modelo {modelo.id!r} revision {revision.id!r} has no provider year")
    return build_snapshot(
        modelo,
        catalogues,
        source_root=source_root,
        filing_year=provider_year,
        period=selector.periods[0],
        revision_id=revision.id,
    )


def _current_provider_revision(modelo: ModeloDefinition) -> ModeloRevision:
    open_revisions = tuple(revision for revision in modelo.revisions.values() if revision.valid_to is None)
    candidates = open_revisions or tuple(modelo.revisions.values())
    if not candidates:
        raise FilingBuilderError(f"modelo {modelo.id!r} has no revisions")
    return max(candidates, key=lambda revision: (revision.valid_from, revision.id))


def _collection_from_snapshot(
    snapshot: RegistrySnapshot,
    validator: RegistryValidator,
) -> RegistryCasillaCollection:
    modelo = snapshot.modelo
    revision = snapshot.revision
    validator.validate_modelo(modelo)
    casillas: dict[str, RegistryCasillaSchema] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        casillas[casilla.id] = _casilla_schema(casilla, formulas)
    return RegistryCasillaCollection(
        casillas=tuple(casillas[key] for key in sorted(casillas)),
        schema_version=f"registry:{modelo.id}:{revision.id}",
    )


def _subview_from_snapshot(snapshot: RegistrySnapshot) -> RegistryFilingSubview:
    reconciliation_total_casillas = {
        kind: casilla_id
        for expectation in snapshot.revision.verification_expectations
        for kind, casilla_id in expectation.reconciliation_totals.items()
    }
    return RegistryFilingSubview(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        schema_version=f"registry:{snapshot.modelo.id}:{snapshot.revision.id}",
        cadence=snapshot.modelo.cadence,
        period_selector_periods=snapshot.revision.period_selector.periods,
        legal_ref_ids=tuple(sorted(snapshot.legal)),
        source_ref_ids=tuple(sorted(snapshot.sources)),
        extraction_profile_ids=tuple(sorted(snapshot.extraction_profiles)),
        verification_expectation_ids=tuple(sorted(snapshot.verification_expectations)),
        reconciliation_total_casillas=dict(sorted(reconciliation_total_casillas.items())),
        export_layout_ids=tuple(sorted(layout.id for layout in snapshot.revision.export_layouts)),
        export_layouts=tuple(sorted(snapshot.revision.export_layouts, key=lambda layout: layout.id)),
        application_link_ids=tuple(sorted(snapshot.application_links)),
        deadline_window_ids=tuple(sorted(snapshot.deadline_windows)),
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
    "RegistryFilingSubview",
    "RegistrySchemaProvider",
    "build_runtime_schema_provider",
    "filing_profile_from_autonomo",
    "load_default_filing_profile",
]
