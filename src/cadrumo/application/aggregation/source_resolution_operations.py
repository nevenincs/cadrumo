"""Canonical operations over resolved calculation-source envelopes.

The source-resolution contract lives in :mod:`.source_mesh`; this module owns
the operations that combine resolver results, emit repeated diagnostics and
provenance, and make unresolved or degraded sources explicit.  Keeping those
operations together leaves the envelope module focused on its validated data
contract while preserving one implementation for every merge collision rule.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol

from ...core.aggregation import BindingSourceKind, BindingValueOutcome, CalculationSourceLineageRole
from ...core.casilla_id import CasillaId
from ...core.external_constants import OutputLanguage
from ...core.i18n.translatable import Translatable as tr
from ...core.logging import get_logger
from ...domain.calculations.record_row_membership import ClosedRecordRowSet
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.calculations.registry.binding_provider_registration import registration_for
from ...domain.calculations.registry.binding_targets import sole_bound_casilla
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.ids import BindingId, RelationId
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.row_casilla import DirectRowMaterializationProvenance, RowCasillaKey
from ...domain.calculations.row_source_identity import RowBindingKey, RowSourceIdentity
from ...domain.modelos.calculation_revision_m303_handoff import M303RegimenSimplificadoAnnualSummaryHandoff
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, bound_input_source_ref
from ...domain.modelos.row_models import ModeloDetailRow
from ...domain.modelos.source_disagreement import (
    DisagreementBooleanValue,
    DisagreementDateValue,
    DisagreementDecimalValue,
    DisagreementEnumValue,
    DisagreementRelationValue,
    DisagreementRowsValue,
    DisagreementScalarValue,
    DisagreementTextValue,
    DisagreementValue,
    SourceDisagreementEntry,
    SourceDisagreementRole,
)
from .errors import AggregationValidationError
from .source_diagnostic_reason import CalculationSourceDiagnosticReason
from .source_mesh import (
    BorradorSourceProvenance,
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
    CompositeSourceResolverId,
    RowBindingValue,
)
from .source_precedence import PRECEDENCE_OVERLAY_ORDER

_log = get_logger(__name__)


class _SourceIssue(Protocol):
    @property
    def reason(self) -> object: ...

    @property
    def detail(self) -> str: ...


def _no_source_text(_: object) -> None:
    return None


def _no_note_fact(_: object) -> None:
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
    fact: Callable[[T], CalculationNoteFact | None] = _no_note_fact,
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
            fact=fact(item),
        )
        for item in items
    )


def unresolved_binding_diagnostics(
    *,
    revision: ModeloRevision,
    source_kind: str,
    binding_ids: tuple[BindingId, ...],
    resolver_id: str,
    message: str,
    message_language: OutputLanguage | None = None,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """One diagnostic per unresolved binding, naming the box the binding fills when it fills one.

    ``message_language`` is the language ``message`` was worded in for the filer, when it was.

    ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
    """
    return tuple(
        CalculationSourceDiagnostic(
            reason="unresolved_binding",
            source_kind=source_kind,
            resolver_id=resolver_id,
            binding_id=binding_id,
            casilla_id=sole_bound_casilla(revision, binding_id),
            message=message,
            message_language=message_language,
        )
        for binding_id in binding_ids
    )


def source_issue_diagnostics[T: _SourceIssue](
    issues: Sequence[T],
    *,
    source_kind: str,
    resolver_id: str,
    suppressed_reasons: frozenset[object] = frozenset(),
    held_back_reasons: frozenset[object] = frozenset(),
    source_ref: Callable[[T], str | None] = _no_source_text,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Project typed aggregation issues, optionally excluding known non-advisories."""
    return tuple(
        CalculationSourceDiagnostic(
            reason="source_domain_not_ready" if issue.reason in held_back_reasons else "source_issue",
            source_kind=source_kind,
            resolver_id=resolver_id,
            message=issue.detail,
            source_ref=source_ref(issue) if issue.reason in held_back_reasons else None,
        )
        for issue in issues
        if issue.reason not in suppressed_reasons
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


class PrecedenceKeyKind(StrEnum):
    """What a precedence key names: a binding, a relation fold or a bound casilla input."""

    BINDING = "binding"
    RELATION = "relation"
    CASILLA = "casilla"


@dataclass(frozen=True, slots=True)
class TierValueProvenance:
    """Where one tier's value for one key came from.

    ``source_ref`` names the source object without disclosing it, and
    ``evidence_ref`` is the fingerprint or snapshot id the value was read from.
    """

    source_family: str
    source_ref: str | None = None
    evidence_ref: str | None = None


def _no_tier_provenance() -> Mapping[str, TierValueProvenance]:
    empty: dict[str, TierValueProvenance] = {}
    return MappingProxyType(empty)


@dataclass(frozen=True, slots=True)
class PrecedenceTier:
    """One tier of the precedence overlay: the role it plays, what it resolved, and where its values came from.

    ``source_family`` names the tier's values where ``provenance`` names no
    more exact family for a key. ``provenance`` is keyed by the binding,
    relation or casilla the value is for.
    """

    role: SourceDisagreementRole
    resolution: CalculationSourceResolution
    source_family: str
    provenance: Mapping[str, TierValueProvenance] = field(default_factory=_no_tier_provenance)


@dataclass(frozen=True, slots=True)
class TierDivergence:
    """A higher tier replaced a different value a lower tier held for the same key.

    ``sources`` lists every tier that held a value for the key, lowest first,
    each with its typed value; ``selected_role`` is the tier whose value the
    overlay kept. ``differing_row_indices`` names the rows that differ when the
    key is a row binding.
    """

    key: str
    key_kind: PrecedenceKeyKind
    value_channel: str
    sources: tuple[SourceDisagreementEntry, ...]
    selected_role: SourceDisagreementRole
    differing_row_indices: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class PrecedenceOverlay:
    """The overlaid resolution, every divergence the overlay found, and the tier each binding's value came from."""

    resolution: CalculationSourceResolution
    divergences: tuple[TierDivergence, ...]
    selected_binding_roles: Mapping[BindingId, SourceDisagreementRole]


@dataclass(frozen=True, slots=True)
class _Holding:
    """One tier's value for one key, held so the overlay can compare it with the tiers above."""

    role: SourceDisagreementRole
    entry: SourceDisagreementEntry
    comparable: object


_TEXT_VALUE_LIMIT = 512
"""The longest text a disagreement states; equality is always decided on the full text."""


def _scalar_disagreement_value(value: RowBindingValue) -> DisagreementScalarValue:
    """State one row cell in its own type; a truth value is tested before ``int``, its base class."""
    if isinstance(value, bool):
        return DisagreementBooleanValue(value=value)
    if isinstance(value, Decimal):
        return DisagreementDecimalValue.of(value)
    if isinstance(value, int):
        return DisagreementDecimalValue.of(Decimal(value))
    return DisagreementTextValue(value=value[:_TEXT_VALUE_LIMIT])


def _comparable_cell(value: RowBindingValue) -> tuple[str, object]:
    """The key two row cells are equal under: numbers numerically, truth values and text exactly."""
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, Decimal | int):
        return ("decimal", Decimal(value))
    return ("text", value)


type _RowCells = tuple[tuple[int, RowBindingValue], ...]


def _differing_row_indices(selected: _RowCells, lower: _RowCells) -> tuple[int, ...]:
    """The row indices at which two row sets differ: a row only one set has, or a row whose cells differ."""
    selected_by_index = {index: _comparable_cell(value) for index, value in selected}
    lower_by_index = {index: _comparable_cell(value) for index, value in lower}
    return tuple(
        index
        for index in sorted(set(selected_by_index) | set(lower_by_index))
        if selected_by_index.get(index) != lower_by_index.get(index)
    )


def _entry(tier: PrecedenceTier, key: str, value: DisagreementValue) -> SourceDisagreementEntry:
    provenance = tier.provenance.get(key)
    return SourceDisagreementEntry(
        role=tier.role,
        source_family=tier.source_family if provenance is None else provenance.source_family,
        resolver_id=str(tier.resolution.resolver_id),
        source_ref=None if provenance is None else provenance.source_ref,
        value=value,
        evidence_ref=None if provenance is None else provenance.evidence_ref,
    )


@dataclass(slots=True)
class _PrecedenceScreen:
    """Every tier's value for every key, compared once all tiers are laid down."""

    holdings: dict[tuple[PrecedenceKeyKind, str, str], list[_Holding]] = field(default_factory=dict)
    row_holdings: dict[BindingId, list[tuple[_Holding, _RowCells]]] = field(default_factory=dict)
    roles_seen: list[SourceDisagreementRole] = field(default_factory=list)

    def admit(self, role: SourceDisagreementRole) -> None:
        """Refuse a tier laid out of the declared overlay order, or a role laid twice."""
        if role not in PRECEDENCE_OVERLAY_ORDER or (
            self.roles_seen
            and PRECEDENCE_OVERLAY_ORDER.index(self.roles_seen[-1]) >= PRECEDENCE_OVERLAY_ORDER.index(role)
        ):
            raise AggregationValidationError(
                tr("aggregation.source_mesh.errors.precedence_tier_out_of_order"),
                context={"previous_role": self.roles_seen[-1].value if self.roles_seen else None, "role": role.value},
            )
        self.roles_seen.append(role)

    def hold(
        self,
        tier: PrecedenceTier,
        *,
        key: tuple[PrecedenceKeyKind, str, str],
        value: DisagreementValue,
        comparable: object,
    ) -> None:
        self.holdings.setdefault(key, []).append(
            _Holding(role=tier.role, entry=_entry(tier, key[1], value), comparable=comparable)
        )

    def hold_rows(self, tier: PrecedenceTier, rows: Mapping[RowBindingKey, RowBindingValue]) -> None:
        by_binding: dict[BindingId, list[tuple[int, RowBindingValue]]] = {}
        for (binding_id, row_index), value in rows.items():
            by_binding.setdefault(binding_id, []).append((row_index, value))
        for binding_id, cells in by_binding.items():
            ordered = tuple(sorted(cells, key=lambda cell: cell[0]))
            value = DisagreementRowsValue(rows=tuple(_scalar_disagreement_value(cell) for _, cell in ordered))
            holding = _Holding(role=tier.role, entry=_entry(tier, binding_id, value), comparable=None)
            self.row_holdings.setdefault(binding_id, []).append((holding, ordered))

    def divergences(self) -> tuple[TierDivergence, ...]:
        found: list[TierDivergence] = []
        for (key_kind, key, value_channel), held in self.holdings.items():
            selected = held[-1]
            if all(holding.comparable == selected.comparable for holding in held[:-1]):
                continue
            found.append(
                TierDivergence(
                    key=key,
                    key_kind=key_kind,
                    value_channel=value_channel,
                    sources=tuple(holding.entry for holding in held),
                    selected_role=selected.role,
                )
            )
        for binding_id, held_rows in self.row_holdings.items():
            selected_holding, selected_rows = held_rows[-1]
            differing = sorted(
                {index for _, rows in held_rows[:-1] for index in _differing_row_indices(selected_rows, rows)}
            )
            if not differing:
                continue
            found.append(
                TierDivergence(
                    key=binding_id,
                    key_kind=PrecedenceKeyKind.BINDING,
                    value_channel="rows",
                    sources=tuple(holding.entry for holding, _ in held_rows),
                    selected_role=selected_holding.role,
                    differing_row_indices=tuple(differing),
                )
            )
        return tuple(sorted(found, key=lambda divergence: (divergence.key_kind.value, divergence.key)))

    def selected_binding_roles(self) -> dict[BindingId, SourceDisagreementRole]:
        roles: dict[BindingId, SourceDisagreementRole] = {
            key: held[-1].role
            for (key_kind, key, _value_channel), held in self.holdings.items()
            if key_kind is PrecedenceKeyKind.BINDING
        }
        roles.update({binding_id: held_rows[-1][0].role for binding_id, held_rows in self.row_holdings.items()})
        return roles


def _hold_tier_values(screen: _PrecedenceScreen, tier: PrecedenceTier) -> None:
    """Record every value ``tier`` states, on its own channel, before the overlay lays it down."""
    resolution = tier.resolution
    binding = PrecedenceKeyKind.BINDING
    for binding_id, amount in resolution.binding_values.items():
        screen.hold(
            tier,
            key=(binding, binding_id, "decimal"),
            value=DisagreementDecimalValue.of(amount),
            comparable=amount,
        )
    for binding_id, token in resolution.enum_binding_values.items():
        screen.hold(tier, key=(binding, binding_id, "enum"), value=DisagreementEnumValue(token=token), comparable=token)
    for binding_id, day in resolution.date_binding_values.items():
        screen.hold(tier, key=(binding, binding_id, "date"), value=DisagreementDateValue(value=day), comparable=day)
    for binding_id, truth in resolution.boolean_binding_values.items():
        screen.hold(
            tier, key=(binding, binding_id, "boolean"), value=DisagreementBooleanValue(value=truth), comparable=truth
        )
    for relation_id, amount in resolution.relation_values.items():
        screen.hold(
            tier,
            key=(PrecedenceKeyKind.RELATION, relation_id, "relation"),
            value=DisagreementRelationValue.of(amount),
            comparable=amount,
        )
    for casilla_id, amount in resolution.bound_inputs_by_casilla_id.items():
        screen.hold(
            tier,
            key=(PrecedenceKeyKind.CASILLA, casilla_id, "decimal"),
            value=DisagreementDecimalValue.of(amount),
            comparable=amount,
        )
    screen.hold_rows(tier, resolution.row_binding_values)


@dataclass(slots=True)
class _SourceResolutionMergeState:
    """Mutable accumulator for the exclusive source-resolution merge."""

    binding_values: dict[BindingId, Decimal] = field(default_factory=dict)
    enum_binding_values: dict[BindingId, str] = field(default_factory=dict)
    date_binding_values: dict[BindingId, date] = field(default_factory=dict)
    boolean_binding_values: dict[BindingId, bool] = field(default_factory=dict)
    row_binding_values: dict[RowBindingKey, str | Decimal | int | bool] = field(default_factory=dict)
    row_source_identities: dict[RowBindingKey, RowSourceIdentity] = field(default_factory=dict)
    closed_record_row_sets: list[ClosedRecordRowSet] = field(default_factory=list)
    row_casilla_values: dict[RowCasillaKey, Decimal] = field(default_factory=dict)
    row_casilla_provenance: dict[RowCasillaKey, DirectRowMaterializationProvenance] = field(default_factory=dict)
    relation_values: dict[RelationId, Decimal] = field(default_factory=dict)
    unresolved_relation_ids: set[RelationId] = field(default_factory=set)
    unresolved_binding_ids: set[BindingId] = field(default_factory=set)
    inapplicable_binding_ids: set[BindingId] = field(default_factory=set)
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
    bound_input_provenance: dict[CasillaId, CalculationSourceProvenance] = field(default_factory=dict)
    borrador_provenance: BorradorSourceProvenance | None = None
    m303_regimen_simplificado_annual_summary_handoff: M303RegimenSimplificadoAnnualSummaryHandoff | None = None
    value_outcomes: dict[BindingId, BindingValueOutcome] = field(default_factory=dict)
    payment_year_binding_values: dict[BindingId, Decimal] = field(default_factory=dict)
    instalment_basis_binding_values: dict[BindingId, Decimal] = field(default_factory=dict)

    def absorb(self, resolution: CalculationSourceResolution) -> None:
        self._absorb_closed_record_rows(resolution)
        self._absorb_metadata(resolution)
        self._absorb_binding_values(resolution)
        self._absorb_row_binding_values(resolution)
        self._absorb_row_casilla_values(resolution)
        self._absorb_relation_values(resolution)
        self._absorb_bound_inputs(resolution)

    def absorb_by_precedence(self, tier: PrecedenceTier, screen: _PrecedenceScreen) -> None:
        """Overlay one tier, retaining the later tier's value for each key and holding every value for the screen."""
        resolution = tier.resolution
        screen.admit(tier.role)
        _hold_tier_values(screen, tier)
        self._absorb_closed_record_rows(resolution)
        self._absorb_metadata(resolution)
        self._absorb_precedence_values(resolution)
        self._absorb_precedence_row_bindings(resolution)
        self._absorb_precedence_row_casillas(resolution)
        self._absorb_precedence_relations(resolution)
        self.bound_inputs_by_casilla_id.update(resolution.bound_inputs_by_casilla_id)
        self._record_bound_input_sources(resolution)

    def _absorb_closed_record_rows(self, resolution: CalculationSourceResolution) -> None:
        """A source's membership and values cannot be overlaid independently."""
        existing_claims = {binding for row_set in self.closed_record_row_sets for binding in row_set.binding_ids}
        incoming_claims = {binding for row_set in resolution.closed_record_row_sets for binding in row_set.binding_ids}
        existing_values = (
            set(self.binding_values)
            | set(self.enum_binding_values)
            | set(self.date_binding_values)
            | set(self.boolean_binding_values)
            | {binding for binding, _ in self.row_binding_values}
        )
        incoming_values = (
            set(resolution.binding_values)
            | set(resolution.enum_binding_values)
            | set(resolution.date_binding_values)
            | set(resolution.boolean_binding_values)
            | {binding for binding, _ in resolution.row_binding_values}
        )
        if existing_claims.intersection(incoming_claims | incoming_values) or incoming_claims.intersection(
            existing_values
        ):
            raise AggregationValidationError(tr("aggregation.source_mesh.errors.closed_record_rows_conflict"))
        self.closed_record_row_sets.extend(resolution.closed_record_row_sets)

    def _absorb_metadata(self, resolution: CalculationSourceResolution) -> None:
        """Accumulate source facts whose merge rule is independent of value precedence."""
        self.owned_sources.update(resolution.owned_sources)
        self.diagnostics.extend(resolution.diagnostics)
        self.provenance.extend(resolution.provenance)
        self.detail_rows.extend(resolution.detail_rows)
        self.source_transaction_ids.update(resolution.source_transaction_ids)
        self.unresolved_relation_ids.update(resolution.unresolved_relation_ids)
        self.unresolved_binding_ids.update(resolution.unresolved_binding_ids)
        self.inapplicable_binding_ids.update(resolution.inapplicable_binding_ids)
        self.payment_year_binding_values.update(resolution.payment_year_binding_values)
        self.instalment_basis_binding_values.update(resolution.instalment_basis_binding_values)
        if resolution.borrador_provenance is not None:
            self.borrador_provenance = resolution.borrador_provenance
        handoff = resolution.m303_regimen_simplificado_annual_summary_handoff
        if handoff is None:
            return
        if self.m303_regimen_simplificado_annual_summary_handoff is not None:
            raise AggregationValidationError(
                tr("aggregation.source_mesh.errors.annual_summary_handoff_duplicate"),
                context={
                    "first_resolver": self.m303_regimen_simplificado_annual_summary_handoff.source_work_unit_id,
                    "second_resolver": resolution.resolver_id,
                },
            )
        self.m303_regimen_simplificado_annual_summary_handoff = handoff

    def _absorb_precedence_values(self, resolution: CalculationSourceResolution) -> None:
        # An outcome speaks for the value it was stated beside: a later tier's
        # value replaces the earlier outcome along with the earlier value.
        for binding_id in (
            *resolution.binding_values,
            *resolution.enum_binding_values,
            *resolution.date_binding_values,
            *resolution.boolean_binding_values,
        ):
            self.value_outcomes.pop(binding_id, None)
        self.value_outcomes.update(resolution.value_outcomes)
        self.binding_values.update(resolution.binding_values)
        self.enum_binding_values.update(resolution.enum_binding_values)
        self.date_binding_values.update(resolution.date_binding_values)
        self.boolean_binding_values.update(resolution.boolean_binding_values)

    def _absorb_precedence_row_bindings(self, resolution: CalculationSourceResolution) -> None:
        """Lay down a row binding's whole row set from the highest tier that supplies any row of it.

        A row that carries a source identity keeps its exclusive claim, so a
        second tier stating the same row is refused rather than overlaid.
        """
        for row_binding_key in resolution.row_binding_values:
            if row_binding_key in self.row_binding_values and (
                row_binding_key in self.row_source_identities or row_binding_key in resolution.row_source_identities
            ):
                _claim_row_binding(self.row_binding_owners, row_binding_key, resolution.resolver_id)
        replaced = {binding_id for binding_id, _row_index in resolution.row_binding_values}
        for row_binding_key in [key for key in self.row_binding_values if key[0] in replaced]:
            del self.row_binding_values[row_binding_key]
            self.row_source_identities.pop(row_binding_key, None)
            self.row_binding_owners.pop(row_binding_key, None)
        for row_binding_key in resolution.row_binding_values:
            self.row_binding_owners[row_binding_key] = resolution.resolver_id
        self.row_binding_values.update(resolution.row_binding_values)
        self.row_source_identities.update(resolution.row_source_identities)
        self.unresolved_binding_ids.difference_update(replaced)

    def _absorb_precedence_row_casillas(self, resolution: CalculationSourceResolution) -> None:
        for row_casilla_key in resolution.row_casilla_values:
            _claim_row_casilla(self.row_casilla_owners, row_casilla_key, resolution.resolver_id)
        self.row_casilla_values.update(resolution.row_casilla_values)
        self.row_casilla_provenance.update(resolution.row_casilla_provenance)

    def _absorb_precedence_relations(self, resolution: CalculationSourceResolution) -> None:
        self.relation_values.update(resolution.relation_values)
        self.unresolved_relation_ids.difference_update(resolution.relation_values)

    def _absorb_binding_values(self, resolution: CalculationSourceResolution) -> None:
        self.value_outcomes.update(resolution.value_outcomes)
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
        for binding_id, value in resolution.boolean_binding_values.items():
            _claim_binding(self.binding_owners, binding_id, resolution.resolver_id)
            self.boolean_binding_values[binding_id] = value
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
        self._record_bound_input_sources(resolution)

    def _record_bound_input_sources(self, resolution: CalculationSourceResolution) -> None:
        """Name the resolver that supplied each casilla value it handed over directly, apart from any binding.

        A casilla fed this way has no binding for the persisted source trace to
        point at, so each gets its own primary node. A later tier that supplies
        the same casilla replaces the earlier node, as it replaces the value. A
        resolver that owns no single source kind cannot be named, and a casilla
        an inner merge already named keeps that node.
        """
        source = _bound_input_source_kind(resolution)
        if source is None:
            return
        named = {row.source_ref for row in resolution.provenance}
        for casilla_id in resolution.bound_inputs_by_casilla_id:
            if bound_input_source_ref(casilla_id) in named:
                continue
            self.bound_input_provenance[casilla_id] = CalculationSourceProvenance(
                resolver_id=str(resolution.resolver_id),
                resolved_binding_source=source,
                contributor_source_kind=source.value,
                contributor_binding_source=source,
                lineage_role=CalculationSourceLineageRole.PRIMARY,
                source_ref=bound_input_source_ref(casilla_id),
                parent_source_ref=None,
                source_casilla_ids=(casilla_id,),
            )

    def _unresolved_binding_ids(self) -> tuple[BindingId, ...]:
        row_binding_ids = {binding_id for binding_id, _row_index in self.row_binding_values}
        return tuple(
            sorted(
                self.unresolved_binding_ids.difference(
                    self.binding_values,
                    self.enum_binding_values,
                    self.date_binding_values,
                    self.boolean_binding_values,
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
            boolean_binding_values=self.boolean_binding_values,
            row_binding_values=self.row_binding_values,
            row_source_identities=self.row_source_identities,
            closed_record_row_sets=tuple(self.closed_record_row_sets),
            row_casilla_values=self.row_casilla_values,
            row_casilla_provenance=self.row_casilla_provenance,
            relation_values=self.relation_values,
            unresolved_relation_ids=tuple(sorted(self.unresolved_relation_ids.difference(self.relation_values))),
            unresolved_binding_ids=self._unresolved_binding_ids(),
            inapplicable_binding_ids=tuple(self.inapplicable_binding_ids),
            bound_inputs_by_casilla_id=self.bound_inputs_by_casilla_id,
            detail_rows=tuple(self.detail_rows),
            source_transaction_ids=tuple(sorted(self.source_transaction_ids)),
            borrador_provenance=self.borrador_provenance,
            m303_regimen_simplificado_annual_summary_handoff=self.m303_regimen_simplificado_annual_summary_handoff,
            diagnostics=tuple(self.diagnostics),
            provenance=(*self.provenance, *(row for _, row in sorted(self.bound_input_provenance.items()))),
            value_outcomes=self.value_outcomes,
            payment_year_binding_values=self.payment_year_binding_values,
            instalment_basis_binding_values=self.instalment_basis_binding_values,
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
    tiers: Sequence[PrecedenceTier],
    *,
    resolver_id: CompositeSourceResolverId = CompositeSourceResolverId.PRECEDENCE_MESH,
) -> PrecedenceOverlay:
    """Overlay tiers into one source resolution, with later tiers winning values, and report each replacement.

    Tiers arrive in :data:`~.source_precedence.PRECEDENCE_OVERLAY_ORDER`, one
    per role. Every tier's value for every key is compared exactly on its own
    channel: a higher tier replacing a different value a lower tier held is a
    :class:`TierDivergence`. Equal values and a lower tier that holds nothing
    for the key are not. A row binding's rows are compared as one set, first by
    cardinality and then row by row in index order.
    """
    state = _SourceResolutionMergeState()
    screen = _PrecedenceScreen()
    for tier in tiers:
        state.absorb_by_precedence(tier, screen)
    return PrecedenceOverlay(
        resolution=state.to_resolution(resolver_id),
        divergences=screen.divergences(),
        selected_binding_roles=MappingProxyType(screen.selected_binding_roles()),
    )


def collect_unhandled_source_diagnostics(
    revision: ModeloRevision,
    *,
    handled_sources: frozenset[str],
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Return diagnostics for revision bindings with no enrolled resolver.

    A kind whose provider registration is ``non_runtime`` -- an operator's
    typed value, a constant the record design fixes -- is enrolled on the route
    with nothing to run, so it never needs a resolver and is never reported. A
    ``deferred`` kind is reported as deferred; every other kind outside
    ``handled_sources`` is reported as unhandled.

    Core types:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`.
    """
    diagnostics: list[CalculationSourceDiagnostic] = []
    for binding in revision.bindings:
        source = str(binding.source)
        if source in handled_sources:
            continue
        disposition = registration_for(binding.source).disposition
        if disposition == "non_runtime":
            continue
        if disposition == "deferred":
            diagnostics.append(
                CalculationSourceDiagnostic(
                    reason="deferred_binding_source",
                    source_kind=source,
                    binding_id=binding.id,
                    message=f"binding {binding.id!r} declares deferred source {source!r}",
                ),
            )
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


@contextmanager
def source_context_operation(context: CalculationSourceContext) -> Generator[PinnedAuthorityOperation]:
    """Reuse a caller's lease; admit one only for a standalone resolver boundary."""
    if context.operation is not None:
        with validating_governed_facts(context.operation):
            yield context.operation
        return
    with bundled_indexed_authority().operation() as operation:
        yield operation


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
                message=tr("errors.integrity.integrity_storage_secure_object_unreadable"),
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
        tr("aggregation.source_mesh.errors.duplicate_binding_owner"),
        context={"binding_id": binding_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_row_binding(owners: dict[RowBindingKey, str], row_binding_key: RowBindingKey, resolver_id: str) -> None:
    existing = owners.get(row_binding_key)
    if existing is None:
        owners[row_binding_key] = resolver_id
        return
    binding_id, row_index = row_binding_key
    raise AggregationValidationError(
        tr("aggregation.source_mesh.errors.duplicate_row_binding_owner"),
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
        tr("aggregation.source_mesh.errors.duplicate_row_casilla_owner"),
        context={
            "casilla_id": casilla_id,
            "row_index": row_index,
            "first_resolver": existing,
            "second_resolver": resolver_id,
        },
    )


def _bound_input_source_kind(resolution: CalculationSourceResolution) -> BindingSourceKind | None:
    """Return the one source kind a resolution's direct casilla values rest on, when it owns exactly one."""
    kinds = set(resolution.owned_sources) or {row.resolved_binding_source for row in resolution.provenance}
    return next(iter(kinds)) if len(kinds) == 1 else None


def _claim_bound_casilla(owners: dict[CasillaId, str], casilla_id: CasillaId, resolver_id: str) -> None:
    existing = owners.get(casilla_id)
    if existing is None:
        owners[casilla_id] = resolver_id
        return
    raise AggregationValidationError(
        tr("aggregation.source_mesh.errors.duplicate_bound_casilla_owner"),
        context={"casilla_id": casilla_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


def _claim_relation(owners: dict[RelationId, str], relation_id: RelationId, resolver_id: str) -> None:
    existing = owners.get(relation_id)
    if existing is None:
        owners[relation_id] = resolver_id
        return
    raise AggregationValidationError(
        tr("aggregation.source_mesh.errors.duplicate_relation_owner"),
        context={"relation_id": relation_id, "first_resolver": existing, "second_resolver": resolver_id},
    )


__all__ = [
    "PrecedenceKeyKind",
    "PrecedenceOverlay",
    "PrecedenceTier",
    "TierDivergence",
    "TierValueProvenance",
    "collect_unhandled_source_diagnostics",
    "flatten_source_provenance_for",
    "merge_source_resolutions",
    "merge_source_resolutions_by_precedence",
    "sorted_source_ids",
    "source_context_operation",
    "source_diagnostics_for",
    "source_issue_diagnostics",
    "source_provenance_for",
    "storage_degradation_resolution",
    "unresolved_binding_diagnostics",
]
