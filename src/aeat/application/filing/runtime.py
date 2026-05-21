"""Production runtime helpers for :mod:`aeat.application.filing`.

Exposes concrete profile helpers used by the CLI and workflow surfaces.
The production schema provider requires validated registry snapshots.

The filing runtime must not depend on
:mod:`aeat.application.filing.testing`; this module is the production
entry point that callers (CLI, workflow, services) construct profiles
and schema providers through.

Key entry points:

* :class:`ModeloOperatorProfile` — pydantic v2 record satisfying the
  filing-profile Protocol.
* :func:`filing_profile_from_taxpayer` — projects taxpayer identity from a
  domain :class:`aeat.domain.deadlines.TaxpayerProfile` into the runtime
  profile shape without deriving legal filing obligations.
* :func:`load_default_filing_profile` — loads the active profile bucket
  and returns a runtime profile.
* :func:`build_runtime_schema_provider` — requires registry-backed snapshots.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check required by Modelo 100 snapshots.
import aeat.domain.renta as _renta_snapshot_checks  # noqa: F401

from ...core.resources import bundled_path
from ...domain.calculations.registry import (
    CasillaDefinition,
    ExportLayoutDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
    RegistrySnapshotError,
    ValidatedRegistryAuthority,
    expression_casilla_refs,
)
from ...domain.calculations.registry._ids import CasillaId, FormulaId, LegalRefId, SourceRefId
from ...domain.filing import CasillaCollection, CasillaSchema
from ...domain.filing._errors import ModeloBuilderError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class TaxpayerProfileIdentity(Protocol):
    """Structural identity surface accepted by the filing profile projector."""

    @property
    def tax_id(self) -> str:
        """Tax identity copied into the filing runtime profile."""
        ...


class ModeloOperatorProfile(BaseModel):
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


class RegistryCasillaSchema(BaseModel):
    """Filing schema projection for one registry casilla.

    Strict, frozen pydantic v2 projection preserving typed IDs,
    ``Decimal`` bounds, and the regulatory grounding (``legal_refs``,
    ``source_refs``) from the authoritative :class:`CasillaDefinition`.
    """

    model_config = _STRICT_FROZEN

    id: CasillaId
    value_type: str
    required: bool
    formula: FormulaId | None
    formula_inputs: tuple[CasillaId, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    min_value: Decimal | None = None
    max_value: Decimal | None = None
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
class RegistryModeloSubview:
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
    subviews: dict[str, RegistryModeloSubview]

    def get_collection(self, modelo: str) -> CasillaCollection:
        try:
            return self.collections[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(f"modelo {modelo!r} is not present in the calculation registry") from exc

    def get_subview(self, modelo: str) -> RegistryModeloSubview:
        """Return the validated registry subview backing ``modelo``."""

        try:
            return self.subviews[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(f"modelo {modelo!r} is not present in the calculation registry") from exc


def filing_profile_from_taxpayer(
    profile: TaxpayerProfileIdentity,
    *,
    display_name: str | None = None,
) -> ModeloOperatorProfile:
    """Project an :class:`TaxpayerProfile` into a :class:`ModeloOperatorProfile`.

    This helper deliberately copies only taxpayer identity. Modelo
    applicability is legal filing truth and must come from validated
    registry data, not a filing-runtime tuple or the deadline engine.

    Args:
        profile: Source domain profile.
        display_name: Optional friendly label; defaults to
            ``profile.tax_id``.

    Returns:
        A frozen :class:`ModeloOperatorProfile`.
    """
    return ModeloOperatorProfile(
        tax_id=profile.tax_id,
        display_name=(display_name or profile.tax_id).strip(),
    )


def load_default_filing_profile(
    *,
    display_name: str | None = None,
) -> ModeloOperatorProfile:
    """Load the active profile bucket for runtime filing commands.

    Resolves the active workflow profile via the wizard descriptor's
    typed projection and re-shapes it as a runtime
    :class:`ModeloOperatorProfile`. Operator profile values stored in
    the profile bucket are the single source of truth.

    Args:
        display_name: Optional friendly label propagated to the
            returned profile.

    Returns:
        The loaded :class:`ModeloOperatorProfile`.

    Raises:
        ModeloBuilderError: When no profile is active in the workflow
            state.
    """
    from ..wizard._status import WizardStatusError, load_active_taxpayer_profile
    from ..workflow._persistence import workflow_state_repository

    state = workflow_state_repository().load()
    try:
        profile = load_active_taxpayer_profile(state)
    except WizardStatusError as exc:
        raise ModeloBuilderError(str(exc)) from exc
    return filing_profile_from_taxpayer(profile, display_name=display_name)


def build_runtime_schema_provider(
    registry_root: Path | None = None,
    *,
    source_root: Path | None = None,
    filing_year: int | None = None,
    period: str | None = None,
    modelos: Sequence[str] | None = None,
) -> RegistrySchemaProvider:
    """Build the production schema provider from validated registry TOML."""

    root = (registry_root or bundled_path("registry", "aeat")).resolve()
    resolved_source_root = (source_root or bundled_path()).resolve()
    selected_ids = _normalize_modelo_selection(modelos)
    selected_tuple = None if selected_ids is None else tuple(sorted(selected_ids))
    return _build_runtime_schema_provider_cached(
        root,
        resolved_source_root,
        filing_year,
        period,
        selected_tuple,
        _registry_tree_fingerprint(root),
    )


@lru_cache(maxsize=32)
def _build_runtime_schema_provider_cached(
    root: Path,
    resolved_source_root: Path,
    filing_year: int | None,
    period: str | None,
    selected_tuple: tuple[str, ...] | None,
    _fingerprint: tuple[tuple[str, int, int], ...],
) -> RegistrySchemaProvider:
    authority = ValidatedRegistryAuthority.load(root, source_root=resolved_source_root)
    loaded_modelos = authority.modelos
    if not loaded_modelos:
        raise ModeloBuilderError(f"registry root has no modelo definitions: {root}")
    if selected_tuple is not None:
        selected_ids = set(selected_tuple)
        by_id = {modelo.id: modelo for modelo in loaded_modelos}
        missing = sorted(selected_ids.difference(by_id))
        if missing:
            raise ModeloBuilderError(f"registry root is missing requested modelo definitions: {missing!r}")
        loaded_modelos = tuple(by_id[modelo_id] for modelo_id in selected_tuple)
    snapshots: dict[str, RegistrySnapshot] = {}
    for modelo in loaded_modelos:
        try:
            snapshots[modelo.id] = _snapshot_for_provider(
                authority,
                modelo,
                filing_year=filing_year,
                period=period,
            )
        except RegistrySnapshotError:
            if filing_year is None or period is None:
                raise
            continue
    if not snapshots:
        raise ModeloBuilderError(f"registry root has no modelo definitions for year={filing_year} period={period!r}")
    return RegistrySchemaProvider(
        collections={modelo_id: _collection_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        subviews={modelo_id: _subview_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
    )


def _registry_tree_fingerprint(root: Path) -> tuple[tuple[str, int, int], ...]:
    paths = sorted((root / "legal").rglob("*.toml")) + sorted((root / "modelos").rglob("*.toml"))
    fingerprint: list[tuple[str, int, int]] = []
    for path in paths:
        stat = path.stat()
        fingerprint.append((path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size))
    return tuple(fingerprint)


def _normalize_modelo_selection(modelos: Sequence[str] | None) -> set[str] | None:
    if modelos is None:
        return None
    selected = {modelo.strip() for modelo in modelos}
    if "" in selected:
        raise ModeloBuilderError("requested modelo selection must not contain blank modelo ids")
    return selected


def _snapshot_for_provider(
    authority: ValidatedRegistryAuthority,
    modelo: ModeloDefinition,
    *,
    filing_year: int | None,
    period: str | None,
) -> RegistrySnapshot:
    if (filing_year is None) != (period is None):
        raise ModeloBuilderError("filing_year and period must be supplied together")
    if filing_year is not None and period is not None:
        return authority.snapshot(modelo.id, filing_year=filing_year, period=period)
    revision = _current_provider_revision(modelo)
    selector = revision.period_selector
    provider_year = selector.years[0] if selector.years else selector.year_from
    if provider_year is None:
        raise ModeloBuilderError(f"modelo {modelo.id!r} revision {revision.id!r} has no provider year")
    return authority.snapshot(
        modelo.id,
        filing_year=provider_year,
        period=selector.periods[0],
        revision_id=revision.id,
    )


def _current_provider_revision(modelo: ModeloDefinition) -> ModeloRevision:
    open_revisions = tuple(revision for revision in modelo.revisions.values() if revision.valid_to is None)
    candidates = open_revisions or tuple(modelo.revisions.values())
    if not candidates:
        raise ModeloBuilderError(f"modelo {modelo.id!r} has no revisions")
    return max(candidates, key=lambda revision: (revision.valid_from, revision.id))


def _collection_from_snapshot(snapshot: RegistrySnapshot) -> RegistryCasillaCollection:
    modelo = snapshot.modelo
    revision = snapshot.revision
    casillas: dict[str, RegistryCasillaSchema] = {}
    formulas = {formula.id: formula for formula in revision.formulas}
    for casilla in revision.casillas:
        casillas[casilla.id] = _casilla_schema(casilla, formulas)
    return RegistryCasillaCollection(
        casillas=tuple(casillas[key] for key in sorted(casillas)),
        schema_version=f"registry:{modelo.id}:{revision.id}",
    )


def _subview_from_snapshot(snapshot: RegistrySnapshot) -> RegistryModeloSubview:
    reconciliation_total_casillas = {
        kind: casilla_id
        for expectation in snapshot.revision.verification_expectations
        for kind, casilla_id in expectation.reconciliation_totals.items()
    }
    return RegistryModeloSubview(
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
    formula_inputs: tuple[CasillaId, ...] = ()
    if casilla.formula is not None:
        formula = formulas[casilla.formula]
        formula_inputs = tuple(dict.fromkeys(expression_casilla_refs(formula.expression)))
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    if casilla.constraints is not None:
        min_value = casilla.constraints.min_value
        max_value = casilla.constraints.max_value
    return RegistryCasillaSchema(
        id=casilla.id,
        value_type=_value_type(casilla.data_type),
        required=casilla.required,
        formula=casilla.formula,
        formula_inputs=formula_inputs,
        legal_refs=casilla.legal_refs,
        source_refs=casilla.source_refs,
        min_value=min_value,
        max_value=max_value,
    )


def _value_type(data_type: str) -> str:
    if data_type in {"decimal", "money", "ratio"}:
        return "decimal"
    if data_type in {"integer", "year"}:
        return "int"
    if data_type in {
        "text",
        "nif",
        "nif_iva",
        "name",
        "period_code",
        "country_code",
        "province_code",
        "municipality_code",
        "postal_code",
        "iban",
    }:
        return "str"
    if data_type == "boolean":
        return "bool"
    if data_type == "date":
        return "date"
    raise ModeloBuilderError(f"unsupported registry casilla data type {data_type!r}")


__all__ = [
    "ModeloOperatorProfile",
    "RegistryCasillaCollection",
    "RegistryCasillaSchema",
    "RegistryModeloSubview",
    "RegistrySchemaProvider",
    "build_runtime_schema_provider",
    "filing_profile_from_taxpayer",
    "load_default_filing_profile",
]
