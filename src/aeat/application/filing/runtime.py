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

The schema provider consumes a :class:`RegistrySnapshot` built from a
:class:`ModeloRevision` within a :class:`ModeloDefinition`, accessed through
a :class:`ValidatedRegistryAuthority` loaded from the configured registry root.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.resources import bundled_path

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check required by Modelo 100 snapshots.
from ...domain.calculations.registry import (
    CasillaDefinition,
    CasillaId,
    ExportLayoutDefinition,
    FormulaDefinition,
    FormulaId,
    LegalRefId,
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
    RegistrySnapshotError,
    SourceRefId,
    ValidatedRegistryAuthority,
    expression_casilla_refs,
    revision_reference_identity_failures,
)
from ...domain.filing import CasillaCollection, CasillaSchema, ModeloBuilderError


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

    casilla_id: CasillaId
    value_type: str
    required: bool
    formula: FormulaId | None
    formula_input_casilla_ids: tuple[CasillaId, ...]
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

    def __post_init__(self) -> None:
        """Reject ambiguous or dangling casilla schema references at construction."""
        ids = tuple(casilla.casilla_id for casilla in self.casillas)
        duplicates = tuple(sorted(casilla_id for casilla_id, count in Counter(ids).items() if count > 1))
        if duplicates:
            raise ModeloBuilderError(
                "runtime casilla schema contains duplicate casilla.id values; registry projection is ambiguous",
                translated_message="application.filing.runtime.errors.ambiguous_casilla_schema",
                context={"schema_version": self.schema_version, "casilla_ids": ",".join(duplicates)},
            )

        known_ids = frozenset(ids)
        dangling_formula_input_casilla_ids = {
            casilla.casilla_id: tuple(
                input_id for input_id in casilla.formula_input_casilla_ids if input_id not in known_ids
            )
            for casilla in self.casillas
            if casilla.formula_input_casilla_ids
        }
        dangling_formula_input_casilla_ids = {
            casilla_id: missing for casilla_id, missing in dangling_formula_input_casilla_ids.items() if missing
        }
        if dangling_formula_input_casilla_ids:
            details = "; ".join(
                f"{casilla_id}: {','.join(missing)}"
                for casilla_id, missing in sorted(dangling_formula_input_casilla_ids.items())
            )
            raise ModeloBuilderError(
                "runtime casilla schema formula inputs must reference canonical casilla.id values in the same schema",
                translated_message="application.filing.runtime.errors.ambiguous_casilla_schema",
                context={"schema_version": self.schema_version, "casilla_ids": details},
            )

    def __iter__(self) -> object:
        """Iterate over the contained :class:`RegistryCasillaSchema` instances."""
        return iter(self.casillas)

    def get(self, casilla_id: CasillaId) -> CasillaSchema | None:
        """Return the :class:`CasillaSchema` for ``casilla_id``, or ``None`` if absent."""
        for casilla in self.casillas:
            if casilla.casilla_id == casilla_id:
                return casilla
        return None

    def all(self) -> Sequence[CasillaSchema]:
        """Return all casilla schemas in declaration order.

        Each element is a :class:`CasillaSchema`.
        """
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
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId]
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
        """Return the casilla collection for ``modelo``.

        Returns a :class:`CasillaCollection` for the modelo.
        Raises :exc:`ModeloBuilderError` when the modelo is absent.
        """
        try:
            return self.collections[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(
                f"modelo {modelo!r} is not present in the calculation registry",
                translated_message="application.filing.runtime.errors.modelo_not_in_registry",
                context={"modelo": modelo},
            ) from exc

    def get_subview(self, modelo: str) -> RegistryModeloSubview:
        """Return the :class:`RegistryModeloSubview` backing ``modelo``."""
        try:
            return self.subviews[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(
                f"modelo {modelo!r} is not present in the calculation registry",
                translated_message="application.filing.runtime.errors.modelo_not_in_registry",
                context={"modelo": modelo},
            ) from exc


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
        raise ModeloBuilderError(
            "active filing profile could not be loaded",
            translated_message="application.filing.runtime.errors.active_profile_load_failed",
            context={"reason": exc.__class__.__name__},
        ) from exc
    return filing_profile_from_taxpayer(profile, display_name=display_name)


def build_runtime_schema_provider(
    registry_root: Path | None = None,
    *,
    source_root: Path | None = None,
    filing_year: int | None = None,
    period: Period | None = None,
    modelos: Sequence[str] | None = None,
) -> RegistrySchemaProvider:
    """Build and return the :class:`RegistrySchemaProvider` from validated registry TOML."""
    _validate_period_arguments(filing_year=filing_year, period=period)
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
    period: Period | None,
    selected_tuple: tuple[str, ...] | None,
    _fingerprint: tuple[tuple[str, int, int], ...],
) -> RegistrySchemaProvider:
    authority = ValidatedRegistryAuthority.load(root, source_root=resolved_source_root)
    loaded_modelos = authority.modelos
    if not loaded_modelos:
        raise ModeloBuilderError(
            "registry root has no modelo definitions",
            translated_message="application.filing.runtime.errors.registry_empty",
            context={"registry_root_name": root.name},
        )
    if selected_tuple is not None:
        selected_ids = set(selected_tuple)
        by_id = {modelo.id: modelo for modelo in loaded_modelos}
        missing = sorted(selected_ids.difference(by_id))
        if missing:
            raise ModeloBuilderError(
                f"registry root is missing requested modelo definitions: {missing!r}",
                translated_message="application.filing.runtime.errors.registry_missing_requested_modelos",
                context={"modelos": ", ".join(missing)},
            )
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
        raise ModeloBuilderError(
            f"registry root has no modelo definitions for year={filing_year} period={period!r}",
            translated_message="application.filing.runtime.errors.registry_empty_for_period",
            context={"filing_year": str(filing_year), "period": str(period)},
        )
    return RegistrySchemaProvider(
        collections={modelo_id: _collection_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        subviews={modelo_id: _subview_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
    )


_FINGERPRINT_CACHE: dict[Path, tuple[float, tuple[tuple[str, int, int], ...]]] = {}


def clear_runtime_fingerprint_cache() -> None:
    """Clear the time-based TTL cache for registry tree fingerprints."""
    _FINGERPRINT_CACHE.clear()


def _registry_tree_fingerprint(  # ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE
    root: Path,
) -> tuple[tuple[str, int, int], ...]:
    # ALT-FINGERPRINT-RATIONALE-REGISTRY-TREE:
    # relative-path keyed for tree-walk change detection (distinct from
    # filename-keyed canonical file_stat_fingerprint).
    import time

    now = time.time()
    if root in _FINGERPRINT_CACHE:
        cached_time, cached_val = _FINGERPRINT_CACHE[root]
        if now - cached_time < 1.0:
            return cached_val

    paths = sorted((root / "legal").rglob("*.toml")) + sorted((root / "modelos").rglob("*.toml"))
    fingerprint: list[tuple[str, int, int]] = []
    for path in paths:
        stat = path.stat()
        fingerprint.append((path.relative_to(root).as_posix(), stat.st_mtime_ns, stat.st_size))
    val = tuple(fingerprint)
    _FINGERPRINT_CACHE[root] = (now, val)
    return val


def _normalize_modelo_selection(modelos: Sequence[str] | None) -> set[str] | None:
    if modelos is None:
        return None
    selected = {modelo.strip() for modelo in modelos}
    if "" in selected:
        raise ModeloBuilderError(
            "requested modelo selection must not contain blank modelo ids",
            translated_message="application.filing.runtime.errors.blank_modelo_selection",
        )
    return selected


def _validate_period_arguments(*, filing_year: int | None, period: Period | None) -> None:
    if filing_year is None and period is None:
        return
    if filing_year is None or period is None:
        raise ModeloBuilderError(
            "filing_year and period must be supplied together",
            translated_message="application.filing.runtime.errors.filing_year_period_pair",
        )
    if not isinstance(period, Period):
        raise ModeloBuilderError(
            "runtime schema provider requires period as aeat.core.Period",
            translated_message="application.filing.runtime.errors.period_type",
            context={"period_type": type(period).__name__},
        )
    if filing_year != period.filing_year:
        raise ModeloBuilderError(
            "filing_year must match the supplied Period",
            translated_message="application.filing.runtime.errors.filing_year_period_mismatch",
            context={"filing_year": str(filing_year), "period": str(period)},
        )


def _snapshot_for_provider(
    authority: ValidatedRegistryAuthority,
    modelo: ModeloDefinition,
    *,
    filing_year: int | None,
    period: Period | None,
) -> RegistrySnapshot:
    if filing_year is not None and period is not None:
        return authority.snapshot(modelo.id, filing_year=filing_year, period=period.registry_token)
    revision = _current_provider_revision(modelo)
    selector = revision.period_selector
    provider_year = selector.years[0] if selector.years else selector.year_from
    if provider_year is None:
        raise ModeloBuilderError(
            f"modelo {modelo.id!r} revision {revision.id!r} has no provider year",
            translated_message="application.filing.runtime.errors.provider_year_missing",
            context={"modelo": modelo.id, "revision": revision.id},
        )
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
        raise ModeloBuilderError(
            f"modelo {modelo.id!r} has no revisions",
            translated_message="application.filing.runtime.errors.modelo_revision_missing",
            context={"modelo": modelo.id},
        )
    return max(candidates, key=lambda revision: (revision.valid_from, revision.id))


def _collection_from_snapshot(snapshot: RegistrySnapshot) -> RegistryCasillaCollection:
    modelo = snapshot.modelo
    revision = snapshot.revision
    schema_version = f"registry:{modelo.id}:{revision.id}"
    identity_failures = revision_reference_identity_failures(f"runtime schema {schema_version}", revision)
    if identity_failures:
        raise ModeloBuilderError(
            "runtime schema revision identity is ambiguous; registry projection cannot continue:\n"
            + "\n".join(f" - {failure}" for failure in identity_failures),
            translated_message="application.filing.runtime.errors.ambiguous_casilla_schema",
            context={
                "schema_version": schema_version,
                "modelo": modelo.id,
                "revision_id": revision.id,
                "filing_year": snapshot.filing_year,
                "period": snapshot.period,
                "casilla_ids": "; ".join(identity_failures),
            },
        )
    formulas = {formula.id: formula for formula in revision.formulas}
    casillas = tuple(
        sorted((_casilla_schema(casilla, formulas) for casilla in revision.casillas), key=lambda c: c.casilla_id),
    )
    return RegistryCasillaCollection(
        casillas=casillas,
        schema_version=schema_version,
    )


def _subview_from_snapshot(snapshot: RegistrySnapshot) -> RegistryModeloSubview:
    reconciliation_total_casilla_ids = {
        kind: casilla_id
        for expectation in snapshot.revision.verification_expectations
        for kind, casilla_id in expectation.reconciliation_total_casilla_ids.items()
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
        reconciliation_total_casilla_ids=dict(sorted(reconciliation_total_casilla_ids.items())),
        export_layout_ids=tuple(sorted(layout.id for layout in snapshot.revision.export_layouts)),
        export_layouts=tuple(sorted(snapshot.revision.export_layouts, key=lambda layout: layout.id)),
        application_link_ids=tuple(sorted(snapshot.application_links)),
        deadline_window_ids=tuple(sorted(snapshot.deadline_windows)),
    )


def _casilla_schema(
    casilla: CasillaDefinition,
    formulas: dict[str, FormulaDefinition],
) -> RegistryCasillaSchema:
    formula_input_casilla_ids: tuple[CasillaId, ...] = ()
    if casilla.formula is not None:
        formula = formulas[casilla.formula]
        formula_input_casilla_ids = tuple(dict.fromkeys(expression_casilla_refs(formula.expression)))
    min_value: Decimal | None = None
    max_value: Decimal | None = None
    if casilla.constraints is not None:
        min_value = casilla.constraints.min_value
        max_value = casilla.constraints.max_value
    return RegistryCasillaSchema(
        casilla_id=casilla.id,
        value_type=_value_type(casilla.data_type),
        required=casilla.required,
        formula=casilla.formula,
        formula_input_casilla_ids=formula_input_casilla_ids,
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
    raise ModeloBuilderError(
        f"unsupported registry casilla data type {data_type!r}",
        translated_message="application.filing.runtime.errors.unsupported_casilla_data_type",
        context={"data_type": data_type},
    )


__all__ = [
    "ModeloOperatorProfile",
    "RegistryCasillaCollection",
    "RegistryCasillaSchema",
    "RegistryModeloSubview",
    "RegistrySchemaProvider",
    "build_runtime_schema_provider",
    "clear_runtime_fingerprint_cache",
    "filing_profile_from_taxpayer",
    "load_default_filing_profile",
]
