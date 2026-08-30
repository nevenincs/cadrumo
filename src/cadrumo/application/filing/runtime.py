"""Production runtime helpers for :mod:`application.filing`.

Exposes concrete profile helpers used by the CLI and workflow surfaces.
The production schema provider requires validated registry snapshots and
projects them into the :class:`~domain.filing.CasillaSchemaProvider`
surface consumed by :func:`~application.filing.build_draft`.

This module is the production entry point through which callers (CLI,
workflow, services) construct profiles and schema providers.

Key entry points:

* :class:`ModeloOperatorProfile` — pydantic v2 record satisfying the
  filing-profile Protocol.
* :func:`filing_profile_from_taxpayer` — projects taxpayer identity from a
  domain :class:`~domain.deadlines.TaxpayerProfile` into the runtime
  profile shape without deriving legal filing obligations.
* :func:`load_default_filing_profile` — loads the active profile bucket
  and returns a runtime profile.
* :func:`build_runtime_schema_provider` — requires registry-backed snapshots.

The schema provider consumes a
:class:`~domain.calculations.registry.RegistrySnapshot` built from a
:class:`~domain.calculations.registry.ModeloRevision` within a
:class:`~domain.calculations.registry.ModeloDefinition`, accessed through
a :class:`~domain.calculations.registry.ValidatedRegistryAuthority` loaded
from the configured registry root.

See Also:
    :func:`application.wizard.status.load_active_taxpayer_profile`
        Active-profile bridge that supplies the
        :class:`domain.deadlines.TaxpayerProfile` projected here.
    :mod:`application.modelo._workflow_gate`
        Calculation-revision workflow gate that uses this runtime provider to
        build and approve filing drafts.
    :mod:`application.modelo._revision_replay_inputs`
        Converts stored calculation revisions into the flat filing inputs
        accepted by this runtime surface.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core import Period
from ...core.casilla_id import CasillaId
from ...core.aggregation import BindingSourceKind
from ...core.identity import SubjectTaxId
from ...core.resources import bundled_path
from ...domain.calculations.registry.authority import ValidatedRegistryAuthority
from ...domain.calculations.registry.errors import (
    RegistryFailureCondition,
    RegistrySnapshotError,
    RegistryValidationError,
)
from ...domain.calculations.registry.ids import (
    FormulaId,
    LegalRefId,
    RevisionId,
    SourceRefId,
)
from ...domain.calculations.registry.loader_fingerprints import (
    clear_fingerprint_cache as _clear_loader_fingerprint_cache,
)
from ...domain.calculations.registry.rate_box_partition import (
    RateBoxPartition,
    derive_rate_box_partitions,
)
from ...domain.calculations.registry.runtime_graph import expression_casilla_refs
from ...domain.calculations.registry.schema import (
    DataBindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.calculations.registry.schema_references import SourceReference
from ...domain.calculations.registry.schema_scalars import registry_scalar_value_type

# Importing the renta package registers the first-slice routing
# cross-domain snapshot check required by Modelo 100 snapshots.
from ...domain.calculations.registry.schema_surfaces import (
    CalculationCompletenessManifest,
    CasillaConstraints,
    CasillaDefinition,
)
from ...domain.calculations.registry.schema_verification import fold_reconciliation_total_casilla_ids
from ...domain.calculations.registry.validate_revision_identity import revision_reference_identity_failures
from ...domain.filing.protocols import CasillaCollection, CasillaSchema
from ...domain.filing.schema import registry_schema_version
from .errors import ModeloApplicationError as ModeloBuilderError


def _empty_source_references() -> dict[SourceRefId, SourceReference]:
    """Create the typed empty source-reference map used by the runtime accessor."""
    return {}


class TaxpayerProfileIdentity(Protocol):
    """Structural identity surface accepted by the filing profile projector."""

    @property
    def tax_id(self) -> SubjectTaxId:
        """Validated tax identity copied into the filing runtime profile."""
        ...


class ModeloOperatorProfile(BaseModel):
    """Concrete runtime implementation of the filing-profile Protocol.

    Strict, frozen pydantic v2 model satisfying the filing layer's
    profile Protocol.

    Attributes:
        tax_id: Validated NIF / NIE / CIF of the filing operator.
        display_name: Human-readable label for the profile.
    """

    model_config = _STRICT_FROZEN

    tax_id: SubjectTaxId = Field(min_length=1)
    display_name: str = Field(min_length=1)


class RegistryCasillaSchema(BaseModel):
    """Filing schema projection for one registry casilla.

    Strict, frozen pydantic v2 projection preserving typed IDs,
    complete :class:`~domain.calculations.registry.CasillaConstraints` contract
    and regulatory grounding (``legal_refs``, ``source_refs``) from the authoritative
    :class:`~domain.calculations.registry.CasillaDefinition`.
    """

    model_config = _STRICT_FROZEN

    casilla_id: CasillaId
    value_type: str
    required: bool
    formula: FormulaId | None
    formula_input_casilla_ids: tuple[CasillaId, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]
    constraints: CasillaConstraints | None = None
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
        """Return all casilla schemas ordered by canonical ``casilla_id``.

        Deliberately not registry declaration order: the loader compiles
        ``revision.casillas`` in casilla-fragment filename order, so declaration
        order tracks the corpus layout rather than anything the filing surface
        should depend on. :func:`collection_from_snapshot` sorts by canonical id
        so this projection stays stable under a fragment rename.

        Each element is a :class:`CasillaSchema`.
        """
        return self.casillas


@dataclass(frozen=True, slots=True)
class CasillaRecordMetadata:
    """Registry-declared official record-design metadata for one casilla.

    Projected verbatim from the authoritative
    :class:`~domain.calculations.registry.CasillaDefinition` — the same
    authority the calculation engine consumes — so the fichero-BOE export parity
    gate can re-ground the rendered casilla's number and segmento against the
    registry declaration at the render choke point rather than trusting the
    completeness manifest's own copy of that metadata.

    Attributes:
        casilla_id: Canonical registry casilla identity.
        number: AEAT record-design casilla number.
        segmento: AEAT record-segment code for multi-segment modelos, or
            ``None`` for single-segment modelos.
    """

    casilla_id: CasillaId
    number: str
    segmento: str | None


@dataclass(frozen=True, slots=True)
class RegistryModeloSubview:
    """Snapshot-backed filing details for one modelo revision."""

    modelo_id: str
    revision_id: RevisionId
    schema_version: str
    cadence: str
    period_selector_periods: tuple[str, ...]
    legal_ref_ids: tuple[LegalRefId, ...]
    source_ref_ids: tuple[SourceRefId, ...]
    extraction_profile_ids: tuple[str, ...]
    verification_expectation_ids: tuple[str, ...]
    reconciliation_total_casilla_ids: Mapping[Literal["ingresar", "devolver"], CasillaId]
    export_layout_ids: tuple[str, ...]
    export_layouts: tuple[ExportLayoutDefinition, ...]
    application_link_ids: tuple[str, ...]
    deadline_window_ids: tuple[str, ...]
    completeness_manifest: CalculationCompletenessManifest | None
    casilla_record_metadata: tuple[CasillaRecordMetadata, ...] = ()
    rate_box_partitions: tuple[RateBoxPartition, ...] = ()
    """Two-layer rate partitions the revision declares: one rate-blind total
    casilla and the rate-specific casillas that break it down.

    A derivation, not a second copy of the binding set: the whole ledger-IVA
    binding tuple would make this a shadow snapshot, so what is carried is only
    the pairing the export gate needs. The gate refuses a return whose rate boxes
    account for less than their total, and it cannot re-derive the pairing itself
    without a revision it does not hold.

    Empty for every revision declaring no rate-specific binding, which is every
    revision until a modelo splits a tier casilla into its box and total layers.
    """
    profile_export_bindings: tuple[DataBindingDefinition, ...] = ()
    """Profile bindings that declare an address on the exported record.

    Deliberately NOT every profile binding: only those carrying a
    ``dictionary_field``, which is what makes a binding addressable on the
    exported declaration. A subview carrying the whole binding set would stop
    being a projection and start being a second snapshot, which is the shape the
    registry authority owns and this class must not duplicate.

    The export header composer reads these to populate the identity slots AEAT's
    dictionary names, so the join is driven by the registry's own declarations
    rather than by a hand-written map per field.
    """

    def has_completeness_manifest(self) -> bool:
        """Return whether this revision carries a calculation-completeness manifest.

        The manifest is the AEAT Diseño de Registros calculation-closure
        projection (:class:`CalculationCompletenessManifest`) that grounds the
        fichero-BOE export parity gate. A revision without one cannot have its
        `.boe` export checked for casilla completeness, so the export path
        surfaces a coverage advisory rather than asserting parity.
        """
        return self.completeness_manifest is not None


@dataclass(frozen=True, slots=True)
class RegistrySchemaAccessor:
    """Registry-backed filing schema accessor.

    The concrete registry-schema accessor (it provides casilla collections
    and modelo subviews from validated registry TOML); structurally
    satisfies the :class:`~domain.filing.CasillaSchemaProvider` protocol.
    Named an accessor to stay distinct from the settled calculate-mesh resolver
    port.
    """

    collections: Mapping[str, RegistryCasillaCollection]
    subviews: Mapping[str, RegistryModeloSubview]
    snapshots: Mapping[str, RegistrySnapshot]
    source_root: Path | None = None
    sources: Mapping[SourceRefId, SourceReference] = field(default_factory=_empty_source_references)

    def __post_init__(self) -> None:
        """Retain one immutable, internally consistent snapshot selection."""
        snapshot_ids = frozenset(self.snapshots)
        if not snapshot_ids:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.registry_empty",
                context={"reason": "snapshot-free-accessor"},
            )
        if frozenset(self.collections) != snapshot_ids or frozenset(self.subviews) != snapshot_ids:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.ambiguous_casilla_schema",
                context={"modelos": ", ".join(sorted(snapshot_ids))},
            )
        for modelo_id, snapshot in self.snapshots.items():
            subview = self.subviews[modelo_id]
            collection = self.collections[modelo_id]
            if (
                snapshot.modelo.id != modelo_id
                or snapshot.revision.id != subview.revision_id
                or collection.schema_version != subview.schema_version
            ):
                raise ModeloBuilderError(
                    translated_message="application.filing.runtime.errors.ambiguous_casilla_schema",
                    context={"modelo": modelo_id},
                )
        object.__setattr__(self, "collections", MappingProxyType(dict(self.collections)))
        object.__setattr__(self, "subviews", MappingProxyType(dict(self.subviews)))
        object.__setattr__(self, "snapshots", MappingProxyType(dict(self.snapshots)))
        object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))

    def get_collection(self, modelo: str) -> CasillaCollection:
        """Return the casilla collection for ``modelo``.

        Returns a :class:`~domain.filing.CasillaCollection` for the modelo.
        Raises :exc:`~domain.filing.ModeloBuilderError` when the modelo is
        absent.
        """
        try:
            return self.collections[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.modelo_not_in_registry",
                context={"modelo": modelo},
            ) from exc

    def get_subview(self, modelo: str) -> RegistryModeloSubview:
        """Return the :class:`RegistryModeloSubview` backing ``modelo``."""
        try:
            return self.subviews[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.modelo_not_in_registry",
                context={"modelo": modelo},
            ) from exc

    def get_snapshot(self, modelo: str) -> RegistrySnapshot:
        """Return the exact immutable registry snapshot selected for ``modelo``."""
        try:
            return self.snapshots[modelo]
        except KeyError as exc:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.modelo_not_in_registry",
                context={"modelo": modelo},
            ) from exc


def filing_profile_from_taxpayer(
    profile: TaxpayerProfileIdentity,
    *,
    display_name: str | None = None,
) -> ModeloOperatorProfile:
    """Project taxpayer identity into a :class:`ModeloOperatorProfile`.

    The common caller passes
    :class:`~domain.deadlines.TaxpayerProfile`, but the accepted contract is
    the narrower :class:`TaxpayerProfileIdentity` Protocol. This helper
    deliberately copies only taxpayer identity. Modelo applicability is legal
    filing truth and must come from validated registry data, not a filing-runtime
    tuple or the deadline engine.

    Args:
        profile: Source identity object exposing ``tax_id``.
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
    from ..wizard.status import (
        WizardStatusError,
        load_active_taxpayer_profile,
    )
    from ..workflow.persistence import workflow_state_repository

    state = workflow_state_repository().load()
    try:
        profile = load_active_taxpayer_profile(state)
    except WizardStatusError as exc:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.active_profile_load_failed",
            context={"reason": exc.__class__.__name__},
        ) from exc
    return filing_profile_from_taxpayer(profile, display_name=display_name)


def build_runtime_schema_provider(
    registry_root: Path | None = None,
    *,
    source_root: Path | None = None,
    filing_year: int | None = None,
    period: object | None = None,
    modelos: Sequence[str] | None = None,
) -> RegistrySchemaAccessor:
    """Build a :class:`RegistrySchemaAccessor` from validated registry TOML.

    When ``filing_year`` and ``period`` are supplied, both are required and
    ``period`` must be a typed :class:`~core.Period`; raw registry tokens
    are rejected before snapshot lookup. Without an explicit period, the
    provider selects the current open revision for each modelo.

    Args:
        registry_root: Optional registry root. Defaults to the bundled AEAT
            registry.
        source_root: Optional source-material root used by
            :class:`~domain.calculations.registry.ValidatedRegistryAuthority`.
        filing_year: Optional filing year; must be paired with ``period``.
        period: Optional typed :class:`~core.Period`; must match
            ``filing_year``.
        modelos: Optional modelo id selection. Blank ids are rejected.

    Returns:
        A :class:`RegistrySchemaAccessor` implementing the filing
        :class:`~domain.filing.CasillaSchemaProvider` surface.

    Raises:
        :class:`~domain.filing.ModeloBuilderError`: When the registry is
            empty, a requested modelo is missing, the period arguments are
            invalid, or no snapshot exists for the requested filing context.
    """
    validated_period = _validate_period_arguments(filing_year=filing_year, period=period)
    root = (registry_root or bundled_path("registry", "aeat")).resolve()
    resolved_source_root = (source_root or bundled_path()).resolve()
    selected_ids = _normalize_modelo_selection(modelos)
    selected_tuple = None if selected_ids is None else tuple(sorted(selected_ids))
    return _build_runtime_schema_provider_cached(
        root,
        resolved_source_root,
        filing_year,
        validated_period,
        selected_tuple,
        registry_tree_fingerprint(root),
    )


@lru_cache(maxsize=32)
def _build_runtime_schema_provider_cached(
    root: Path,
    resolved_source_root: Path,
    filing_year: int | None,
    period: Period | None,
    selected_tuple: tuple[str, ...] | None,
    _fingerprint: tuple[tuple[str, int, int], ...],
) -> RegistrySchemaAccessor:
    authority = ValidatedRegistryAuthority.load(root, source_root=resolved_source_root)
    loaded_modelos = authority.modelos
    if not loaded_modelos:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_empty",
            context={"registry_root_name": root.name},
        )
    if selected_tuple is not None:
        selected_ids = set(selected_tuple)
        by_id = {modelo.id: modelo for modelo in loaded_modelos}
        missing = sorted(selected_ids.difference(by_id))
        if missing:
            raise ModeloBuilderError(
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
        except (RegistrySnapshotError, RegistryValidationError) as exc:
            if _is_below_filing_authority(exc):
                if selected_tuple is None:
                    continue
                # The caller NAMED this modelo, so silently dropping it and then
                # reporting an empty registry describes the wrong problem: the
                # registry holds the modelo, it just declares a lower rung than
                # a filing draft needs. Propagating the registry's own refusal
                # keeps the modelo, its revision and both grades in the message.
                raise
            if filing_year is None or period is None:
                raise _registry_snapshot_unavailable_error(
                    modelo=modelo,
                    filing_year=filing_year,
                    period=period,
                    exc=exc,
                ) from exc
            continue
    if not snapshots:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_empty_for_period",
            context={"filing_year": str(filing_year), "period": str(period)},
        )
    return RegistrySchemaAccessor(
        collections={modelo_id: collection_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        subviews={modelo_id: _subview_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        snapshots=snapshots,
        source_root=resolved_source_root,
        sources=dict(authority.catalogues.sources),
    )


def _registry_snapshot_unavailable_error(
    *,
    modelo: ModeloDefinition,
    filing_year: int | None,
    period: Period | None,
    exc: RegistrySnapshotError | RegistryValidationError,
) -> ModeloBuilderError:
    """Translate a rejected provider snapshot into the filing error surface.

    ``RegistrySnapshot`` is filing-grade by definition.  A provider request
    without an explicit filing context still needs to refuse a revision whose
    legal slice is not filing-grade, but it must do so through the filing
    boundary's typed error rather than leaking the registry implementation
    exception to callers.
    """
    return ModeloBuilderError(
        translated_message="application.filing.build_draft.errors.registry_snapshot_unavailable",
        context={
            "modelo": modelo.id,
            "filing_year": filing_year,
            "period": period.registry_token if period is not None else None,
            "registry_error_type": type(exc).__name__,
        },
    )


_FINGERPRINT_CACHE: dict[Path, tuple[float, tuple[tuple[str, int, int, str], ...]]] = {}


def clear_runtime_fingerprint_cache() -> None:
    """Clear the time-based TTL cache for registry tree fingerprints.

    Also clears the canonical collector's own cache
    (:func:`~domain.calculations.registry.clear_fingerprint_cache`).
    ``registry_tree_fingerprint`` now delegates its walk to that collector,
    which carries its own path-keyed TTL cache underneath this module's
    one-second wrapper; clearing only the outer layer would leave a caller
    that mutates the registry tree and calls this function still served a
    stale collector-cached value, exactly the correctness hole this
    delegation exists to close.
    """
    _FINGERPRINT_CACHE.clear()
    _clear_loader_fingerprint_cache()


def registry_tree_fingerprint(
    root: Path,
) -> tuple[tuple[str, int, int, str], ...]:
    """Return the TTL-cached registry tree fingerprint for runtime schema loading.

    Delegates the walk to the canonical
    :func:`~cadrumo.domain.calculations.registry.collect_registry_tree_fingerprints`,
    rather than a second hand-rolled tree walk: that collector adds a content
    digest for mutable (non-bundled) trees specifically because
    ``(size, mtime_ns)`` alone cannot distinguish two successive writes of
    the same byte length within one coarse filesystem mtime tick, and
    exempts the digest for the package-bundled tree (read-only, never
    rewritten in-process) so the common case pays only per-file call
    overhead, not hashing. It is used as a cache key for
    :func:`build_runtime_schema_provider`; call
    :func:`clear_runtime_fingerprint_cache` when tests or tooling mutate the
    registry tree inside the one-second TTL this module's own cache holds
    (the collector's own, longer-lived cache for the bundled root is a
    separate, per-path layer this TTL sits in front of).
    """
    import time

    now = time.monotonic()
    if root in _FINGERPRINT_CACHE:
        cached_time, cached_val = _FINGERPRINT_CACHE[root]
        if now - cached_time < 1.0:
            return cached_val

    from ...domain.calculations.registry.loader import collect_registry_tree_fingerprints

    val = collect_registry_tree_fingerprints(root)
    _FINGERPRINT_CACHE[root] = (now, val)
    return val


def _normalize_modelo_selection(modelos: Sequence[str] | None) -> set[str] | None:
    if modelos is None:
        return None
    selected = {modelo.strip() for modelo in modelos}
    if "" in selected:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.blank_modelo_selection",
        )
    return selected


def _validate_period_arguments(*, filing_year: int | None, period: object | None) -> Period | None:
    if filing_year is None and period is None:
        return None
    if filing_year is None or period is None:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.filing_year_period_pair",
        )
    if not isinstance(period, Period):
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.period_type",
            context={"period_type": type(period).__name__},
        )
    if filing_year != period.filing_year:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.filing_year_period_mismatch",
            context={"filing_year": str(filing_year), "period": str(period)},
        )
    return period


def _is_below_filing_authority(exc: Exception) -> bool:
    """Report whether one snapshot refusal was a grade insufficiency, not a defect.

    This provider serves filing drafts, so it asks the registry for FILING
    authority. A modelo whose revision declares a lower rung -- modelo 036,
    whose censal alta/modificacion/baja is filed on AEAT's sede and produces no
    fichero here -- is not a filing-draft schema at all, and an unfiltered sweep
    that raised on it made the whole provider unbuildable. An explicitly
    requested modelo still raises: the caller named it.
    """
    classification = getattr(exc, "registry_failure", None)
    return (
        classification is not None
        and classification.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
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
            translated_message="application.filing.runtime.errors.modelo_revision_missing",
            context={"modelo": modelo.id},
        )
    return max(candidates, key=lambda revision: (revision.valid_from, revision.id))


def collection_from_snapshot(snapshot: RegistrySnapshot) -> RegistryCasillaCollection:
    """Project a validated registry snapshot into a runtime casilla collection.

    Args:
        snapshot: The
            :class:`~domain.calculations.registry.RegistrySnapshot` whose
            :class:`~domain.calculations.registry.ModeloRevision` is
            projected into filing-runtime casilla schemas.

    Returns:
        A :class:`RegistryCasillaCollection` with the snapshot revision's
        casillas and ``registry:{modelo}:{revision}`` schema version.

    Raises:
        :class:`~domain.filing.ModeloBuilderError`: When the snapshot
            revision contains ambiguous casilla references and cannot be
            projected safely.
    """
    modelo = snapshot.modelo
    revision = snapshot.revision
    schema_version = registry_schema_version(modelo=modelo.id, revision_id=revision.id)
    identity_failures = revision_reference_identity_failures(f"runtime schema {schema_version}", revision)
    if identity_failures:
        raise ModeloBuilderError(
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
    formulas_by_id = {formula.id: formula for formula in revision.formulas}
    formulas_by_target: dict[CasillaId, FormulaDefinition] = {}
    for formula in revision.formulas:
        formulas_by_target.setdefault(formula.target_casilla_id, formula)
    casillas = tuple(
        sorted(
            (_casilla_schema(casilla, formulas_by_id, formulas_by_target) for casilla in revision.casillas),
            key=lambda c: c.casilla_id,
        ),
    )
    return RegistryCasillaCollection(
        casillas=casillas,
        schema_version=schema_version,
    )


def _subview_from_snapshot(snapshot: RegistrySnapshot) -> RegistryModeloSubview:
    reconciliation_total_casilla_ids = fold_reconciliation_total_casilla_ids(
        snapshot.revision.verification_expectations,
    )
    return RegistryModeloSubview(
        modelo_id=snapshot.modelo.id,
        revision_id=snapshot.revision.id,
        schema_version=registry_schema_version(
            modelo=snapshot.modelo.id,
            revision_id=snapshot.revision.id,
        ),
        cadence=snapshot.modelo.cadence,
        period_selector_periods=snapshot.revision.period_selector.periods,
        legal_ref_ids=tuple(sorted(snapshot.legal)),
        source_ref_ids=tuple(sorted(snapshot.sources)),
        extraction_profile_ids=tuple(sorted(snapshot.extraction_profiles)),
        verification_expectation_ids=tuple(sorted(snapshot.verification_expectations)),
        reconciliation_total_casilla_ids=reconciliation_total_casilla_ids,
        export_layout_ids=tuple(sorted(layout.id for layout in snapshot.revision.export_layouts)),
        export_layouts=tuple(sorted(snapshot.revision.export_layouts, key=lambda layout: layout.id)),
        application_link_ids=tuple(sorted(snapshot.application_links)),
        deadline_window_ids=tuple(sorted(snapshot.deadline_windows)),
        completeness_manifest=snapshot.revision.completeness_manifest,
        casilla_record_metadata=tuple(
            CasillaRecordMetadata(
                casilla_id=casilla.id,
                number=casilla.number,
                segmento=casilla.segmento,
            )
            for casilla in snapshot.revision.casillas
        ),
        profile_export_bindings=tuple(
            sorted(
                (binding for binding in snapshot.revision.bindings if _is_profile_export_binding(binding)),
                key=lambda binding: binding.id,
            ),
        ),
        rate_box_partitions=derive_rate_box_partitions(snapshot.revision),
    )


def _is_profile_export_binding(binding: DataBindingDefinition) -> bool:
    """Whether ``binding`` names a profile fact addressable on the exported record.

    ``dictionary_field`` is the discriminator because it is what gives a binding
    somewhere to land: a profile binding without one feeds the calculation and
    has no export address at all, which is the same distinction
    ``_is_calculation_only_profile_binding`` draws on the calculation side.
    """
    return (
        binding.source == BindingSourceKind.PROFILE and getattr(binding.selector, "dictionary_field", None) is not None
    )


def _casilla_schema(
    casilla: CasillaDefinition,
    formulas_by_id: Mapping[FormulaId, FormulaDefinition],
    formulas_by_target: Mapping[CasillaId, FormulaDefinition],
) -> RegistryCasillaSchema:
    formula_input_casilla_ids: tuple[CasillaId, ...] = ()
    formula_id = casilla.formula
    formula = formulas_by_id[formula_id] if formula_id is not None else formulas_by_target.get(casilla.id)
    if formula is not None:
        formula_id = formula.id
        formula_input_casilla_ids = tuple(dict.fromkeys(expression_casilla_refs(formula.expression)))
    return RegistryCasillaSchema(
        casilla_id=casilla.id,
        value_type=registry_value_type(casilla.data_type),
        required=casilla.required,
        formula=formula_id,
        formula_input_casilla_ids=formula_input_casilla_ids,
        legal_refs=casilla.legal_refs,
        source_refs=casilla.source_refs,
        constraints=casilla.constraints,
    )


def registry_value_type(data_type: str) -> str:
    """Map a registry casilla data type to the filing runtime value type.

    Returns one of the value-type tags consumed by
    :class:`domain.filing.CasillaSchema`: ``"decimal"``, ``"int"``,
    ``"str"``, ``"bool"``, or ``"date"``.

    Raises:
        ModeloBuilderError: When ``data_type`` is not a supported registry
            casilla type.
    """
    try:
        return registry_scalar_value_type(data_type)
    except RegistryValidationError as exc:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.unsupported_casilla_data_type",
            context={"data_type": data_type, "registry_error_type": type(exc).__name__},
        ) from exc


__all__ = [
    "CasillaRecordMetadata",
    "ModeloOperatorProfile",
    "RegistryCasillaCollection",
    "RegistryCasillaSchema",
    "RegistryModeloSubview",
    "RegistrySchemaAccessor",
    "build_runtime_schema_provider",
    "clear_runtime_fingerprint_cache",
    "collection_from_snapshot",
    "filing_profile_from_taxpayer",
    "load_default_filing_profile",
    "registry_tree_fingerprint",
    "registry_value_type",
]
