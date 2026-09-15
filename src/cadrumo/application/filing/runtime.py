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
* :func:`build_runtime_schema_provider` — requires registry-backed snapshots.
* :func:`schema_provider_from_authority` — projects an explicitly supplied
  validated authority through the same provider surface.

The schema provider consumes a
:class:`~domain.calculations.registry.RegistrySnapshot` built from a
:class:`~domain.calculations.registry.ModeloRevision` within a
:class:`~domain.calculations.registry.ModeloDefinition`, accessed through
a :class:`~domain.calculations.registry.ValidatedRegistryAuthority` loaded
from the configured registry root.

See Also:
    :mod:`application.modelo._workflow_gate`
        Calculation-revision workflow gate that uses this runtime provider to
        build and approve filing drafts.
    :mod:`application.modelo.revision_replay_inputs`
        Converts stored calculation revisions into the flat filing inputs
        accepted by this runtime surface.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Protocol

from pydantic import BaseModel, Field

from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.period import Period
from ...domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
    ValidatedRegistryAuthority,
    bundled_indexed_authority,
)
from ...domain.calculations.registry.authority_artifact import AuthorityComponentCodecError, AuthorityEvidenceProjection
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
from ...domain.calculations.registry.profile_bindings import ProfileProvider
from ...domain.calculations.registry.rate_box_partition import (
    RateBoxPartition,
    derive_rate_box_partitions,
)
from ...domain.calculations.registry.runtime_graph import expression_casilla_refs
from ...domain.calculations.registry.schema import (
    BindingDefinition,
    FormulaDefinition,
    ModeloDefinition,
    RegistrySnapshot,
)
from ...domain.calculations.registry.schema_base import SettlementDirectionField
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
from ...domain.calculations.registry.source_byte_availability import embedded_source_ids
from ...domain.calculations.registry.tax_id_format import SubjectTaxId
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
        duplicates = _duplicate_casilla_ids(ids)
        if duplicates:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.ambiguous_casilla_schema",
                context={"schema_version": self.schema_version, "casilla_ids": ",".join(duplicates)},
            )

        known_ids = frozenset(ids)
        dangling_formula_input_casilla_ids = _dangling_formula_input_casilla_ids(self.casillas, known_ids=known_ids)
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


def _duplicate_casilla_ids(ids: Sequence[CasillaId]) -> tuple[CasillaId, ...]:
    return tuple(sorted(casilla_id for casilla_id, count in Counter(ids).items() if count > 1))


def _dangling_formula_input_casilla_ids(
    casillas: Sequence[RegistryCasillaSchema],
    *,
    known_ids: frozenset[CasillaId],
) -> dict[CasillaId, tuple[CasillaId, ...]]:
    candidates = {
        casilla.casilla_id: tuple(
            input_id for input_id in casilla.formula_input_casilla_ids if input_id not in known_ids
        )
        for casilla in casillas
        if casilla.formula_input_casilla_ids
    }
    return {casilla_id: missing for casilla_id, missing in candidates.items() if missing}


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
    reconciliation_total_casilla_ids: Mapping[SettlementDirectionField, CasillaId]
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
    profile_export_bindings: tuple[BindingDefinition, ...] = ()
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
    sources: Mapping[SourceRefId, SourceReference] = field(default_factory=_empty_source_references)
    evidence: AuthorityEvidenceProjection = field(default_factory=AuthorityEvidenceProjection)

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

    def source_payload(self, source_ref_id: SourceRefId) -> bytes:
        """Return published authority bytes for one runtime source reference."""
        try:
            return self.evidence.source_bytes(str(source_ref_id))
        except AuthorityComponentCodecError as exc:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.registry_empty",
                context={"reason": f"missing-published-source:{source_ref_id}"},
            ) from exc

    @property
    def source_payloads(self) -> Mapping[str, bytes]:
        """Expose the immutable signed source projection for layout consumers."""
        return MappingProxyType({item.source_reference_id: item.payload for item in self.evidence.sources})

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


def build_runtime_schema_provider(
    *,
    filing_year: int,
    period: object,
    modelos: Sequence[str] | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> RegistrySchemaAccessor:
    """Build a :class:`RegistrySchemaAccessor` from validated snapshots.

    ``filing_year`` and ``period`` are required and ``period`` must be a typed
    :class:`~core.Period`; raw registry tokens are rejected before snapshot lookup.

    The provider has no registry or source-root override: filing flows consume
    the immutable authority bundled with the installed package.

    Args:
        filing_year: Filing year of the draft or request.
        period: Typed :class:`~core.Period` matching ``filing_year``.
        modelos: Optional modelo id selection. Blank ids are rejected.
        operation: Optional generation-pinned indexed authority operation. When
            supplied, ``modelos`` must name the requested models explicitly and
            snapshots are loaded through point revision/directory access.

    Returns:
        A :class:`RegistrySchemaAccessor` implementing the filing
        :class:`~domain.filing.CasillaSchemaProvider` surface.

    Raises:
        :class:`~domain.filing.ModeloBuilderError`: When the registry is
            empty, a requested modelo is missing, the period arguments are
            invalid, or no snapshot exists for the requested filing context.
    """
    validated_period = _validate_period_arguments(filing_year=filing_year, period=period)
    selected_tuple = _selected_modelo_tuple(modelos)
    if operation is not None:
        return _schema_provider_for_operation(
            operation,
            filing_year=filing_year,
            period=validated_period,
            selected_tuple=selected_tuple,
        )
    with bundled_indexed_authority().operation() as indexed_operation:
        return _schema_provider_for_operation(
            indexed_operation,
            filing_year=filing_year,
            period=validated_period,
            selected_tuple=selected_tuple,
        )


def schema_provider_from_authority(
    authority: ValidatedRegistryAuthority,
    *,
    filing_year: int,
    period: object,
    modelos: Sequence[str] | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> RegistrySchemaAccessor:
    """Build a :class:`RegistrySchemaAccessor` from an explicit validated authority.

    Applies the same period validation, modelo selection and snapshot
    projection as :func:`build_runtime_schema_provider`, which delegates here
    with the bundled authority. Callers that hold a separately compiled
    authority (for example a development build of the registry source tree)
    use this entry point to project it through the identical filing surface.

    Args:
        authority: Validated registry authority to project.
        filing_year: Filing year of the draft or request.
        period: Typed :class:`~core.Period` matching ``filing_year``.
        modelos: Optional modelo id selection. Blank ids are rejected.
        operation: Optional generation-pinned indexed authority operation. When
            supplied, it takes precedence over the eager authority for the
            selected model point loads.

    Returns:
        A :class:`RegistrySchemaAccessor` implementing the filing
        :class:`~domain.filing.CasillaSchemaProvider` surface.

    Raises:
        :class:`~domain.filing.ModeloBuilderError`: When the registry is
            empty, a requested modelo is missing, the period arguments are
            invalid, or no snapshot exists for the requested filing context.
    """
    validated_period = _validate_period_arguments(filing_year=filing_year, period=period)
    selected_tuple = _selected_modelo_tuple(modelos)
    if operation is not None:
        return _schema_provider_for_operation(
            operation,
            filing_year=filing_year,
            period=validated_period,
            selected_tuple=selected_tuple,
        )
    return _schema_provider_for_authority(
        authority,
        filing_year=filing_year,
        period=validated_period,
        selected_tuple=selected_tuple,
        registry_root_name="published authority artifact",
    )


def _selected_modelo_tuple(modelos: Sequence[str] | None) -> tuple[str, ...] | None:
    selected_ids = _normalize_modelo_selection(modelos)
    return None if selected_ids is None else tuple(sorted(selected_ids))


def _select_runtime_modelos(
    loaded_modelos: Sequence[ModeloDefinition],
    *,
    selected_tuple: tuple[str, ...] | None,
) -> Sequence[ModeloDefinition]:
    if selected_tuple is None:
        return loaded_modelos
    selected_ids = set(selected_tuple)
    by_id = {modelo.id: modelo for modelo in loaded_modelos}
    missing = sorted(selected_ids.difference(by_id))
    if missing:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_missing_requested_modelos",
            context={"modelos": ", ".join(missing)},
        )
    return tuple(by_id[modelo_id] for modelo_id in selected_tuple)


def _runtime_snapshots_for_modelos(
    authority: ValidatedRegistryAuthority,
    modelos: Sequence[ModeloDefinition],
    *,
    filing_year: int,
    period: Period,
    selected_tuple: tuple[str, ...] | None,
) -> dict[str, RegistrySnapshot]:
    snapshots: dict[str, RegistrySnapshot] = {}
    for modelo in modelos:
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
            continue
    return snapshots


def _schema_provider_for_authority(
    authority: ValidatedRegistryAuthority,
    *,
    filing_year: int,
    period: Period,
    selected_tuple: tuple[str, ...] | None,
    registry_root_name: str,
) -> RegistrySchemaAccessor:
    loaded_modelos = authority.modelos
    if not loaded_modelos:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_empty",
            context={"registry_root_name": registry_root_name},
        )
    loaded_modelos = _select_runtime_modelos(loaded_modelos, selected_tuple=selected_tuple)
    snapshots = _runtime_snapshots_for_modelos(
        authority,
        loaded_modelos,
        filing_year=filing_year,
        period=period,
        selected_tuple=selected_tuple,
    )
    if not snapshots:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_empty_for_period",
            context={"filing_year": str(filing_year), "period": str(period)},
        )
    return RegistrySchemaAccessor(
        collections={modelo_id: collection_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        subviews={modelo_id: subview_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        snapshots=snapshots,
        sources=dict(authority.catalogues.sources),
        evidence=authority.evidence,
    )


def _schema_provider_for_operation(
    operation: PinnedAuthorityOperation,
    *,
    filing_year: int,
    period: Period,
    selected_tuple: tuple[str, ...] | None,
) -> RegistrySchemaAccessor:
    """Project one generation-pinned operation into the filing schema surface.

    An indexed operation intentionally has no bulk model enumeration method.
    Requiring an explicit model selection keeps this provider point-addressed;
    each selected model resolves its directory and exactly one revision through
    the operation before the existing snapshot projections run.
    """
    if selected_tuple is None:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_missing_requested_modelos",
            context={"modelos": "explicit selection required for indexed operation"},
        )
    snapshots: dict[str, RegistrySnapshot] = {}
    for modelo_id in selected_tuple:
        try:
            snapshots[modelo_id] = operation.snapshot(
                modelo_id,
                filing_year=filing_year,
                period=period.registry_token,
            )
        except (RegistrySnapshotError, RegistryValidationError) as exc:
            if _is_below_filing_authority(exc):
                raise
            continue
        except ValueError as exc:
            raise ModeloBuilderError(
                translated_message="application.filing.runtime.errors.registry_missing_requested_modelos",
                context={"modelos": modelo_id},
            ) from exc
    if not snapshots:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.registry_empty_for_period",
            context={"filing_year": str(filing_year), "period": period.registry_token},
        )
    sources = {source_id: source for snapshot in snapshots.values() for source_id, source in snapshot.sources.items()}
    source_evidence = tuple(operation.source_evidence(source_id) for source_id in sorted(embedded_source_ids(sources)))
    evidence = AuthorityEvidenceProjection(sources=source_evidence)
    return RegistrySchemaAccessor(
        collections={modelo_id: collection_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        subviews={modelo_id: subview_from_snapshot(snapshot) for modelo_id, snapshot in snapshots.items()},
        snapshots=snapshots,
        sources=sources,
        evidence=evidence,
    )


def _normalize_modelo_selection(modelos: Sequence[str] | None) -> set[str] | None:
    if modelos is None:
        return None
    selected = {modelo.strip() for modelo in modelos}
    if "" in selected:
        raise ModeloBuilderError(
            translated_message="application.filing.runtime.errors.blank_modelo_selection",
        )
    return selected


def _validate_period_arguments(*, filing_year: int, period: object) -> Period:
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
    filing_year: int,
    period: Period,
) -> RegistrySnapshot:
    return authority.snapshot(modelo.id, filing_year=filing_year, period=period.registry_token)


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


def subview_from_snapshot(snapshot: RegistrySnapshot) -> RegistryModeloSubview:
    """Project a validated snapshot into the modelo subview the filing handoff carries."""
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
        period_selector_periods=snapshot.revision.period_selector.periods_for_year(snapshot.filing_year),
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


def _is_profile_export_binding(binding: BindingDefinition) -> bool:
    """Whether ``binding`` names a profile fact addressable on the exported record.

    ``dictionary_field`` is the discriminator because it is what gives a binding
    somewhere to land: a profile binding without one feeds the calculation and
    has no export address at all, which is the same distinction
    ``_is_calculation_only_profile_binding`` draws on the calculation side.
    """
    return isinstance(binding.provider, ProfileProvider) and binding.provider.dictionary_field is not None


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
    "collection_from_snapshot",
    "filing_profile_from_taxpayer",
    "registry_value_type",
    "subview_from_snapshot",
]
