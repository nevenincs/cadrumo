"""Canonical operations over resolved calculation-source envelopes.

The source-resolution contract lives in :mod:`._source_mesh`; this module owns
the operations that combine resolver results, emit repeated diagnostics and
provenance, and make unresolved or degraded sources explicit.  Keeping those
operations together leaves the envelope module focused on its validated data
contract while preserving one implementation for every merge collision rule.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.logging import get_logger
from ...domain.calculations import DirectRowMaterializationProvenance, RowBindingKey, RowCasillaKey, RowSourceIdentity
from ...domain.calculations.registry.ids import BindingId, RelationId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.modelos.calculation_revision import M303RegimenSimplificadoAnnualSummaryHandoff
from ...domain.modelos.row_models import ModeloDetailRow
from ._source_mesh import (
    BorradorSourceProvenance,
    CalculationSourceDiagnostic,
    CalculationSourceDiagnosticReason,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    CompositeSourceResolverId,
)
from .errors import AggregationValidationError, t

_log = get_logger(__name__)

_log = get_logger(__name__)


class _SourceIssue(Protocol):
    @property
    def reason(self) -> object: ...

    @property
    def detail(self) -> str: ...


def _no_source_text(_: object) -> None:
    return None


def source_diagnostics_for[T](
    items: Iterable[T],
    *,
    reason: CalculationSourceDiagnosticReason,
    source_kind: str,
    resolver_id: str | None,
    message: Callable[[T], str],
    source_ref: Callable[[T], str | None] = _no_source_text,
    remedy: Callable[[T], str | None] = _no_source_text,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project repeated source facts through the diagnostic contract."""
    return tuple(
        CalculationSourceDiagnostic(
            reason=reason,
            source_kind=source_kind,
            resolver_id=resolver_id,
            source_ref=source_ref(item),
            message=message(item),
            remedy=remedy(item),
        )
        for item in items
    )


def source_issue_diagnostics(
    issues: Sequence[_SourceIssue],
    *,
    source_kind: str,
    resolver_id: str,
    suppressed_reasons: frozenset[object] = frozenset(),
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project typed aggregation issues, optionally excluding known non-advisories."""
    return source_diagnostics_for(
        (issue for issue in issues if issue.reason not in suppressed_reasons),
        reason="source_issue",
        source_kind=source_kind,
        resolver_id=resolver_id,
        message=lambda issue: issue.detail,
    )


def source_provenance_for[T](
    items: Iterable[T], project: Callable[[T], CalculationSourceProvenance]
) -> tuple[CalculationSourceProvenance, ...]:
    """Project one provenance record for each source fact."""
    return tuple(project(item) for item in items)


def flatten_source_provenance_for[T](
    items: Iterable[T], project: Callable[[T], Iterable[CalculationSourceProvenance]]
) -> tuple[CalculationSourceProvenance, ...]:
    """Flatten source facts that contribute more than one provenance record."""
    return tuple(provenance for item in items for provenance in project(item))


def sorted_source_ids[T](items: Iterable[T], project: Callable[[T], str]) -> tuple[str, ...]:
    """Return stable identifiers for a source collection."""
    return tuple(sorted(project(item) for item in items))


@dataclass(slots=True)
class _SourceResolutionMergeState:
    """Mutable accumulator for the exclusive source-resolution merge."""

    binding_values: dict[BindingId, Decimal] = field(default_factory=dict)
    enum_binding_values: dict[BindingId, str] = field(default_factory=dict)
    date_binding_values: dict[BindingId, date] = field(default_factory=dict)
    row_binding_values: dict[RowBindingKey, str | Decimal | int | bool] = field(default_factory=dict)
    row_source_identities: dict[RowBindingKey, RowSourceIdentity] = field(default_factory=dict)
    row_casilla_values: dict[RowCasillaKey, Decimal] = field(default_factory=dict)
    row_casilla_provenance: dict[RowCasillaKey, DirectRowMaterializationProvenance] = field(default_factory=dict)
    relation_values: dict[RelationId, Decimal] = field(default_factory=dict)
    unresolved_relation_ids: set[RelationId] = field(default_factory=set)
    unresolved_binding_ids: set[BindingId] = field(default_factory=set)
    bound_inputs_by_casilla_id: dict[CasillaId, Decimal] = field(default_factory=dict)
    detail_rows: list[ModeloDetailRow] = field(default_factory=list)
    source_transaction_ids: set[str] = field(default_factory=set)
    diagnostics: list[CalculationSourceDiagnostic] = field(default_factory=list)
    provenance: list[CalculationSourceProvenance] = field(default_factory=list)
    owned_sources: set[BindingSourceKind] = field(default_factory=set)
    binding_owners: dict[BindingId, str] = field(default_factory=dict)
    row_binding_owners: dict[RowBindingKey, str] = field(default_factory=dict)
    row_casilla_owners: dict[RowCasillaKey, str] = field(default_factory=dict)
    relation_owners: dict[RelationId, str] = field(default_factory=dict)
    casilla_owners: dict[CasillaId, str] = field(default_factory=dict)
    borrador_provenance: BorradorSourceProvenance | None = None
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None

    def absorb(self, resolution: CalculationSourceResolution) -> None:
        self.owned_sources.update(resolution.owned_sources)
        self.diagnostics.extend(resolution.diagnostics)
        self.provenance.extend(resolution.provenance)
        self.detail_rows.extend(resolution.detail_rows)
        self.source_transaction_ids.update(resolution.source_transaction_ids)
        self.unresolved_relation_ids.update(resolution.unresolved_relation_ids)
        self.unresolved_binding_ids.update(resolution.unresolved_binding_ids)
        if resolution.borrador_provenance is not None:
            self.borrador_provenance = resolution.borrador_provenance
        handoff = resolution.m303_regimen_simplificado_annual_summary_handoff
        if handoff is not None:
            if self.m303_regimen_simplificado_annual_summary_handoff is not None:
                raise AggregationValidationError(
                    t("aggregation.source_mesh.errors.annual_summary_handoff_duplicate"),
                    context={
                        "first_resolver": self.m303_regimen_simplificado_annual_summary_handoff.source_work_unit_id,
                        "second_resolver": resolution.resolver_id,
                    },
                )
            self.m303_regimen_simplificado_annual_summary_handoff = handoff
        self._absorb_binding_values(resolution)
        self._absorb_row_binding_values(resolution)
        self._absorb_row_casilla_values(resolution)
        self._absorb_relation_values(resolution)
        self._absorb_bound_inputs(resolution)

    def _absorb_binding_values(self, resolution: CalculationSourceResolution) -> None:
        for binding_id, value in resolution.binding_values.items():
            _claim_binding(self.binding_owners, binding_id, resolution.resolver_id)
            self.binding_values[binding_id] = value
            self.unresolved_binding_ids.discard(binding_id)
        for binding_id, value in resolution.enum_binding_values.items():
            _claim_binding(self.binding_owners, binding_id, resolution.resolver_id)
            self.enum_binding_values[binding_id] = value
            self.unresolved_binding_ids.discard(binding_id)
        for binding_id, value in resolution.date_binding_values.items():
            _claim_binding(self.binding_owners, binding_id, resolution.resolver_id)
            self.date_binding_values[binding_id] = value
            self.unresolved_binding_ids.discard(binding_id)

    def _absorb_row_binding_values(self, resolution: CalculationSourceResolution) -> None:
        for row_binding_key, value in resolution.row_binding_values.items():
            _claim_row_binding(self.row_binding_owners, row_binding_key, resolution.resolver_id)
            self.row_binding_values[row_binding_key] = value
            identity = resolution.row_source_identities.get(row_binding_key)
            if identity is not None:
                self.row_source_identities[row_binding_key] = identity
            self.unresolved_binding_ids.discard(row_binding_key[0])

    def _absorb_row_casilla_values(self, resolution: CalculationSourceResolution) -> None:
        for row_casilla_key, value in resolution.row_casilla_values.items():
            _claim_row_casilla(self.row_casilla_owners, row_casilla_key, resolution.resolver_id)
            self.row_casilla_values[row_casilla_key] = value
            self.row_casilla_provenance[row_casilla_key] = resolution.row_casilla_provenance[row_casilla_key]

    def _absorb_relation_values(self, resolution: CalculationSourceResolution) -> None:
        for relation_id, value in resolution.relation_values.items():
            _claim_relation(self.relation_owners, relation_id, resolution.resolver_id)
            self.relation_values[relation_id] = value
            self.unresolved_relation_ids.discard(relation_id)

    def _absorb_bound_inputs(self, resolution: CalculationSourceResolution) -> None:
        for casilla_id, value in resolution.bound_inputs_by_casilla_id.items():
            _claim_bound_casilla(self.casilla_owners, casilla_id, resolution.resolver_id)
            self.bound_inputs_by_casilla_id[casilla_id] = value

    def _unresolved_binding_ids(self) -> tuple[BindingId, ...]:
        row_binding_ids = {binding_id for binding_id, _row_index in self.row_binding_values}
        return tuple(
            sorted(
                self.unresolved_binding_ids.difference(
                    self.binding_values,
                    self.enum_binding_values,
                    self.date_binding_values,
                    row_binding_ids,
                ),
            ),
        )

    def to_resolution(self, resolver_id: str | CompositeSourceResolverId) -> CalculationSourceResolution:
        return CalculationSourceResolution(
            resolver_id=resolver_id,
            owned_sources=tuple(sorted(self.owned_sources)),
            binding_values=self.binding_values,
            enum_binding_values=self.enum_binding_values,
            date_binding_values=self.date_binding_values,
            row_binding_values=self.row_binding_values,
            row_source_identities=self.row_source_identities,
            row_casilla_values=self.row_casilla_values,
            row_casilla_provenance=self.row_casilla_provenance,
            relation_values=self.relation_values,
            unresolved_relation_ids=tuple(sorted(self.unresolved_relation_ids.difference(self.relation_values))),
            unresolved_binding_ids=self._unresolved_binding_ids(),
            bound_inputs_by_casilla_id=self.bound_inputs_by_casilla_id,
            detail_rows=tuple(self.detail_rows),
            source_transaction_ids=tuple(sorted(self.source_transaction_ids)),
            borrador_provenance=self.borrador_provenance,
            m303_regimen_simplificado_annual_summary_handoff=self.m303_regimen_simplificado_annual_summary_handoff,
            diagnostics=tuple(self.diagnostics),
            provenance=tuple(self.provenance),
        )


def merge_source_resolutions(
    resolutions: Sequence[CalculationSourceResolution],
    *,
    resolver_id: CompositeSourceResolverId = CompositeSourceResolverId.EXCLUSIVE_MESH,
) -> CalculationSourceResolution:
    """Merge resolver outputs and reject ambiguous ownership."""
    state = _SourceResolutionMergeState()
    for resolution in resolutions:
        state.absorb(resolution)
    return state.to_resolution(resolver_id)


def merge_source_resolutions_by_precedence(
    tiers: Sequence[CalculationSourceResolution],
    *,
    resolver_id: CompositeSourceResolverId = CompositeSourceResolverId.PRECEDENCE_MESH,
) -> CalculationSourceResolution:
    """Overlay tiers into one source resolution, with later tiers winning values."""
    binding_values: dict[BindingId, Decimal] = {}
    enum_binding_values: dict[BindingId, str] = {}
    date_binding_values: dict[BindingId, date] = {}
    row_binding_values: dict[RowBindingKey, str | Decimal | int | bool] = {}
    row_source_identities: dict[RowBindingKey, RowSourceIdentity] = {}
    row_casilla_values: dict[RowCasillaKey, Decimal] = {}
    row_casilla_provenance: dict[RowCasillaKey, DirectRowMaterializationProvenance] = {}
    row_casilla_owners: dict[RowCasillaKey, str] = {}
    row_binding_owners: dict[RowBindingKey, str] = {}
    relation_values: dict[RelationId, Decimal] = {}
    unresolved_relation_ids: set[RelationId] = set()
    unresolved_binding_ids: set[BindingId] = set()
    bound_inputs_by_casilla_id: dict[CasillaId, Decimal] = {}
    detail_rows: list[ModeloDetailRow] = []
    source_transaction_ids: set[str] = set()
    diagnostics: list[CalculationSourceDiagnostic] = []
    provenance: list[CalculationSourceProvenance] = []
    owned_sources: set[BindingSourceKind] = set()
    borrador_provenance: BorradorSourceProvenance | None = None
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None

    for tier in tiers:
        owned_sources.update(tier.owned_sources)
        diagnostics.extend(tier.diagnostics)
        provenance.extend(tier.provenance)
        detail_rows.extend(tier.detail_rows)
        source_transaction_ids.update(tier.source_transaction_ids)
        unresolved_relation_ids.update(tier.unresolved_relation_ids)
        unresolved_binding_ids.update(tier.unresolved_binding_ids)
        if tier.borrador_provenance is not None:
            borrador_provenance = tier.borrador_provenance
        if tier.m303_regimen_simplificado_annual_summary_handoff is not None:
            if m303_regimen_simplificado_annual_summary_handoff is not None:
                raise AggregationValidationError(
                    t("aggregation.source_mesh.errors.annual_summary_handoff_duplicate"),
                    context={
                        "first_resolver": m303_regimen_simplificado_annual_summary_handoff.source_work_unit_id,
                        "second_resolver": tier.resolver_id,
                    },
                )
            m303_regimen_simplificado_annual_summary_handoff = tier.m303_regimen_simplificado_annual_summary_handoff
        binding_values.update(tier.binding_values)
        enum_binding_values.update(tier.enum_binding_values)
        date_binding_values.update(tier.date_binding_values)
        for row_binding_key in tier.row_binding_values:
            if row_binding_key in row_binding_values and (
                row_binding_key in row_source_identities or row_binding_key in tier.row_source_identities
            ):
                _claim_row_binding(row_binding_owners, row_binding_key, tier.resolver_id)
            row_binding_owners[row_binding_key] = tier.resolver_id
        row_binding_values.update(tier.row_binding_values)
        row_source_identities.update(tier.row_source_identities)
        for binding_id, _row_index in tier.row_binding_values:
            unresolved_binding_ids.discard(binding_id)
        for row_casilla_key in tier.row_casilla_values:
            _claim_row_casilla(row_casilla_owners, row_casilla_key, tier.resolver_id)
        row_casilla_values.update(tier.row_casilla_values)
        row_casilla_provenance.update(tier.row_casilla_provenance)
        bound_inputs_by_casilla_id.update(tier.bound_inputs_by_casilla_id)
        for relation_id, value in tier.relation_values.items():
            relation_values[relation_id] = value
            unresolved_relation_ids.discard(relation_id)

    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=tuple(sorted(owned_sources)),
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        date_binding_values=date_binding_values,
        row_binding_values=row_binding_values,
        row_source_identities=row_source_identities,
        row_casilla_values=row_casilla_values,
        row_casilla_provenance=row_casilla_provenance,
        relation_values=relation_values,
        unresolved_relation_ids=tuple(sorted(unresolved_relation_ids.difference(relation_values))),
        unresolved_binding_ids=tuple(
            sorted(
                unresolved_binding_ids.difference(
                    binding_values,
                    enum_binding_values,
                    date_binding_values,
                    {binding_id for binding_id, _row_index in row_binding_values},
                ),
            ),
        ),
        bound_inputs_by_casilla_id=bound_inputs_by_casilla_id,
        detail_rows=tuple(detail_rows),
        source_transaction_ids=tuple(sorted(source_transaction_ids)),
        borrador_provenance=borrador_provenance,
        m303_regimen_simplificado_annual_summary_handoff=m303_regimen_simplificado_annual_summary_handoff,
        diagnostics=tuple(diagnostics),
        provenance=tuple(provenance),
    )


def collect_unhandled_source_diagnostics(
    revision: ModeloRevision,
    *,
    handled_sources: frozenset[str],
    manual_sources: frozenset[str] = frozenset({"manual_input"}),
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return diagnostics for revision bindings with no enrolled resolver."""
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding in revision.bindings:
        source = str(binding.source)
        if source in handled_sources or source in manual_sources:
            continue
        diagnostics.append(
            CalculationSourceDiagnostic(
                reason="unhandled_binding_source",
                source_kind=source,
                binding_id=binding.id,
                message=f"binding {binding.id!r} declares source {source!r} with no enrolled resolver",
            ),
        )
    return tuple(diagnostics)


def storage_degradation_resolution(
    *,
    resolver_id: str,
    owned_sources: tuple[BindingSourceKind, ...],
    source_kinds: Sequence[str],
    error: BaseException,
) -> CalculationSourceResolution:
    """Return an empty resolution carrying secure-storage degradation diagnostics."""
    normalized_sources = tuple(sorted({source.strip() for source in source_kinds if source.strip()}))
    _log.debug(
        "source mesh resolver storage degradation resolver_id=%s source_kinds=%s error_type=%s",
        resolver_id,
        ",".join(normalized_sources),
        type(error).__name__,
        exc_info=(type(error), error, error.__traceback__),
    )
    return CalculationSourceResolution(
        resolver_id=resolver_id,
        owned_sources=owned_sources,
        diagnostics=tuple(
            CalculationSourceDiagnostic(
                reason="storage_degraded",
                source_kind=source_kind,
                resolver_id=resolver_id,
                message=t("errors.integrity.integrity_storage_secure_object_unreadable"),
            )
            for source_kind in normalized_sources
        ),
    )


def _claim_binding(owners: dict[BindingId, str], binding_id: BindingId, resolver_id: str) -> None:
    existing = owners.get(binding_id)
    if existing is None:
        owners[binding_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_binding_owner"),
        context={"binding_id": binding_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_row_binding(owners: dict[RowBindingKey, str], row_binding_key: RowBindingKey, resolver_id: str) -> None:
    existing = owners.get(row_binding_key)
    if existing is None:
        owners[row_binding_key] = resolver_id
        return
    binding_id, row_index = row_binding_key
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_row_binding_owner"),
        context={
            "binding_id": binding_id,
            "row_index": row_index,
            "first_resolver": existing,
            "second_resolver": resolver_id,
        },
    )


def _claim_row_casilla(owners: dict[RowCasillaKey, str], row_casilla_key: RowCasillaKey, resolver_id: str) -> None:
    existing = owners.get(row_casilla_key)
    if existing is None:
        owners[row_casilla_key] = resolver_id
        return
    casilla_id, row_index = row_casilla_key
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_row_casilla_owner"),
        context={
            "casilla_id": casilla_id,
            "row_index": row_index,
            "first_resolver": existing,
            "second_resolver": resolver_id,
        },
    )


def _claim_bound_casilla(owners: dict[CasillaId, str], casilla_id: CasillaId, resolver_id: str) -> None:
    existing = owners.get(casilla_id)
    if existing is None:
        owners[casilla_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_bound_casilla_owner"),
        context={"casilla_id": casilla_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_relation(owners: dict[RelationId, str], relation_id: RelationId, resolver_id: str) -> None:
    existing = owners.get(relation_id)
    if existing is None:
        owners[relation_id] = resolver_id
        return
    raise AggregationValidationError(
        t("aggregation.source_mesh.errors.duplicate_relation_owner"),
        context={"relation_id": relation_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


__all__ = [
    "collect_unhandled_source_diagnostics",
    "flatten_source_provenance_for",
    "merge_source_resolutions",
    "merge_source_resolutions_by_precedence",
    "sorted_source_ids",
    "source_diagnostics_for",
    "source_issue_diagnostics",
    "source_provenance_for",
    "storage_degradation_resolution",
]
