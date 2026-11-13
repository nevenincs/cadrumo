"""Source mesh resolver for a saver's interest and dividends from profile positions and linked ledger rows.

The positions say who pays, from which state and the taxpayer's share; the
linked rows say how much net cash each position credited in the ejercicio; the
payer's suffered-withholding record says what was withheld and the gross the
payer certifies. The gross is rebuilt from the rows plus the withholding and
checked against the payer's own gross, per payer and never per position.

Each binding resolves to the sum of its quantity over its record's occurrences,
or stays unresolved with a blocking note that names the payer or position and
the door that settles it. Each row column gives every occurrence of its record
one row; a record a note leaves open gives none. Nothing is guessed: a payer whose figures disagree,
rows with no payer evidence, a payer record that no linked row shows, income
from another state and income in kind all leave the affected boxes open.

The resolver never names a payer by its tax identifier: a note names the payer
by the name the position states, and provenance names a payer record by its
keyed ``payer_ref``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.errors.hierarchy import ProfileAnswerTypeError
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.binding_targets import sole_bound_casilla
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.capital_mobiliario_facts import (
    resolve_capital_mobiliario_concept_vocabulary,
    resolve_capital_mobiliario_withholding_rate,
)
from ...domain.calculations.registry.capital_mobiliario_position_bindings import (
    capital_mobiliario_position_bindings,
    resolve_capital_mobiliario_position_binding_values,
    resolve_capital_mobiliario_row_values,
    revision_declares_capital_mobiliario_position,
)
from ...domain.contribuyente.posicion_facts import POSICION_SECTION, posiciones_from_facts
from ...domain.contribuyente.posicion_record import PosicionRecord
from ...domain.modelos.calculation_revision_sources import (
    CAPITAL_MOBILIARIO_POSITION_REF_PREFIX,
    CalculationNoteFact,
    CalculationNoteSentence,
)
from ...domain.renta.capital_mobiliario_occurrences import (
    AttestedNoWithholding,
    CapitalMobiliarioOccurrence,
    ComputedOccurrence,
    PayerComputed,
    PayerEvidence,
    PayerOutcome,
    PayerRecordEvidence,
    PayerRefusal,
    PayerRefusalKind,
    compute_capital_mobiliario_occurrences,
)
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from .capital_mobiliario_position_join import (
    CapitalMobiliarioJoin,
    CapitalMobiliarioJoinFinding,
    CapitalMobiliarioJoinFindingKind,
    join_capital_mobiliario_positions,
)
from .modelo_bindings_support import STORAGE_DEGRADATION_ERRORS, empty_source_resolution
from .retencion_soportada_repository import RetencionSoportadaPersistenceError, RetencionSoportadaPorts
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation, storage_degradation_resolution

if TYPE_CHECKING:
    from decimal import Decimal

    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol

__all__ = [
    "CAPITAL_MOBILIARIO_PAYER_REF_PREFIX",
    "CapitalMobiliarioPositionSourceResolver",
    "profile_positions",
]

CAPITAL_MOBILIARIO_PAYER_REF_PREFIX: Final = "capital-mobiliario-payer:"
"""The provenance reference of the payer evidence one computation rests on, by keyed ``payer_ref``."""

_SOURCE_KIND: Final = BindingSourceKind.CAPITAL_MOBILIARIO_POSITION
_CLASS: Final = RetencionSoportadaClase.CAPITAL_MOBILIARIO
_POSITION_DOOR: Final = (
    "Add or correct the position with config profile posicion, or link the rows to the right position with "
    "app ledger classify --posicion."
)
_ROW_DOOR: Final = (
    "Correct each row's concept or currency with app ledger classify, or enter these casillas by hand with "
    "the modelo work edit action."
)
_UNCOMPUTED_DOOR: Final = "Enter these casillas by hand with the modelo work edit action."
_PAYER_DOOR: Final = (
    "Record the payer's certificate with app ledger retencion-soportada record, or attest that no payer "
    "withheld with app ledger retencion-soportada attest-absence."
)
_DISAGREEMENT_DOOR: Final = (
    "Correct the payer record with app ledger retencion-soportada record, or the linked rows with "
    "app ledger classify, until the two agree."
)

_JOIN_SENTENCES: Final[Mapping[CapitalMobiliarioJoinFindingKind, tuple[CalculationNoteSentence, str]]] = {
    CapitalMobiliarioJoinFindingKind.POSITION_NOT_HELD: (
        CalculationNoteSentence.CAPITAL_MOBILIARIO_POSITION_NOT_HELD,
        _POSITION_DOOR,
    ),
    CapitalMobiliarioJoinFindingKind.ROW_NOT_READABLE: (
        CalculationNoteSentence.CAPITAL_MOBILIARIO_ROW_NOT_READABLE,
        _ROW_DOOR,
    ),
    CapitalMobiliarioJoinFindingKind.FOREIGN_SOURCE: (
        CalculationNoteSentence.CAPITAL_MOBILIARIO_FOREIGN_SOURCE,
        _UNCOMPUTED_DOOR,
    ),
}
_REFUSAL_SENTENCES: Final[Mapping[PayerRefusalKind, tuple[CalculationNoteSentence, str]]] = {
    PayerRefusalKind.PAYER_EVIDENCE_MISSING: (
        CalculationNoteSentence.CAPITAL_MOBILIARIO_PAYER_EVIDENCE_MISSING,
        _PAYER_DOOR,
    ),
    PayerRefusalKind.PAYER_CHECK_MISMATCH: (
        CalculationNoteSentence.CAPITAL_MOBILIARIO_PAYER_CHECK_MISMATCH,
        _DISAGREEMENT_DOOR,
    ),
    PayerRefusalKind.WITHHOLDING_SUM_MISMATCH: (
        CalculationNoteSentence.CAPITAL_MOBILIARIO_WITHHOLDING_SUM_MISMATCH,
        _DISAGREEMENT_DOOR,
    ),
}


@dataclass(frozen=True, slots=True)
class _Finding:
    """One blocking note and the detail records it leaves open; ``None`` leaves every record open."""

    sentence: CalculationNoteSentence
    remedy: str
    detail_records: frozenset[str] | None
    values: Mapping[str, object]
    rows: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _PayerEvidenceRead:
    records: Mapping[str, RetencionSoportadaRecord]
    attested: bool


def _payer_key(record: RetencionSoportadaRecord) -> str:
    return str(record.payer_tax_id).strip().upper()


def _evidence(read: _PayerEvidenceRead, payer_keys: Iterable[str]) -> dict[str, PayerEvidence]:
    evidence: dict[str, PayerEvidence] = {}
    for key in payer_keys:
        record = read.records.get(key)
        if record is not None:
            evidence[key] = PayerRecordEvidence(record)
        elif read.attested:
            evidence[key] = AttestedNoWithholding()
    return evidence


def _records_of(occurrences: Iterable[CapitalMobiliarioOccurrence]) -> frozenset[str] | None:
    records = frozenset(item.detail_record for item in occurrences)
    return records or None


def _join_finding(item: CapitalMobiliarioJoinFinding) -> _Finding:
    sentence, remedy = _JOIN_SENTENCES[item.kind]
    values: dict[str, object] = {"count": len(item.row_ids), "payer": item.payer_name or item.position_ref}
    if item.kind is CapitalMobiliarioJoinFindingKind.FOREIGN_SOURCE and item.country is not None:
        values["country"] = item.country
    return _Finding(sentence, remedy, item.detail_records, values, item.row_ids)


def _refusal_finding(refusal: PayerRefusal, payer: str, records: frozenset[str] | None) -> _Finding:
    sentence, remedy = _REFUSAL_SENTENCES[refusal.kind]
    values: dict[str, object] = {"payer": payer}
    if refusal.computed is not None and refusal.recorded is not None:
        values["amount"] = refusal.computed
        values["compared_amount"] = refusal.recorded
    return _Finding(sentence, remedy, records, values)


def _payer_name(record: RetencionSoportadaRecord, names: Mapping[str, str]) -> str:
    return names.get(_payer_key(record)) or record.payer_legal_name or record.payer_ref[:12]


@dataclass(frozen=True, slots=True)
class _Computation:
    computed: tuple[ComputedOccurrence, ...]
    findings: tuple[_Finding, ...]
    payers_used: frozenset[str]


def _in_kind_findings(join: CapitalMobiliarioJoin, in_kind: set[str], read: _PayerEvidenceRead) -> list[_Finding]:
    findings: list[_Finding] = []
    for key in sorted(in_kind):
        record = read.records[key]
        affected = _records_of(item for item in join.occurrences if item.payer_key == key)
        findings.append(
            _Finding(
                CalculationNoteSentence.CAPITAL_MOBILIARIO_INCOME_IN_KIND,
                _UNCOMPUTED_DOOR,
                affected,
                {"payer": _payer_name(record, join.payer_names)},
            )
        )
    return findings


def _payers_without_rows_findings(join: CapitalMobiliarioJoin, read: _PayerEvidenceRead) -> list[_Finding]:
    return [
        _Finding(
            CalculationNoteSentence.CAPITAL_MOBILIARIO_PAYER_WITHOUT_ROWS,
            _POSITION_DOOR,
            None,
            {"payer": _payer_name(record, join.payer_names)},
        )
        for key, record in sorted(read.records.items())
        if key not in join.linked_payer_keys
    ]


def _compute(join: CapitalMobiliarioJoin, read: _PayerEvidenceRead, rate: Decimal) -> _Computation:
    """Run the arithmetic for every payer whose evidence admits it; every other payer is a finding."""
    in_kind = {key for key, record in read.records.items() if record.valoracion_especie > 0}
    findings: list[_Finding] = [_join_finding(item) for item in join.findings]
    findings.extend(_in_kind_findings(join, in_kind, read))
    computable = tuple(item for item in join.occurrences if item.payer_key not in in_kind)
    outcomes = compute_capital_mobiliario_occurrences(
        computable, _evidence(read, {item.payer_key for item in computable}), rate
    )
    computed = _sort_outcomes(join, computable, outcomes, findings)
    findings.extend(_payers_without_rows_findings(join, read))
    used = frozenset(item.payer_key for item in computed)
    return _Computation(tuple(computed), tuple(findings), used)


def _sort_outcomes(
    join: CapitalMobiliarioJoin,
    computable: tuple[CapitalMobiliarioOccurrence, ...],
    outcomes: Sequence[PayerOutcome],
    findings: list[_Finding],
) -> list[ComputedOccurrence]:
    """Return each computed payer's occurrences, appending a finding for each refused payer."""
    computed: list[ComputedOccurrence] = []
    for outcome in outcomes:
        if isinstance(outcome, PayerComputed):
            computed.extend(outcome.occurrences)
            continue
        affected = _records_of(item for item in computable if item.payer_key == outcome.payer_key)
        payer = join.payer_names.get(outcome.payer_key, outcome.position_refs[0])
        findings.append(_refusal_finding(outcome, payer, affected))
    return computed


def _row_columns(revision: ModeloRevision) -> frozenset[BindingId]:
    return frozenset(
        binding.id
        for binding, provider in capital_mobiliario_position_bindings(revision)
        if provider.dictionary_field is not None
    )


def _open_bindings(revision: ModeloRevision, findings: Sequence[_Finding]) -> dict[BindingId, list[_Finding]]:
    """Return, per family binding a finding leaves open, the findings that do; row columns included."""
    opened: dict[BindingId, list[_Finding]] = {}
    for binding, provider in capital_mobiliario_position_bindings(revision):
        for finding in findings:
            if (
                finding.detail_records is None
                or provider.detail_record is None
                or provider.detail_record in finding.detail_records
            ):
                opened.setdefault(binding.id, []).append(finding)
    return opened


class CapitalMobiliarioPositionSourceResolver:
    """Resolve the family's bindings from positions, their linked ledger rows and the payers' records."""

    resolver_id: ClassVar[str] = "capital_mobiliario_position"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (_SOURCE_KIND,)

    def __init__(
        self,
        *,
        transaction_repository: TransactionCatalogueRepositoryProtocol,
        retencion_soportada_ports: RetencionSoportadaPorts,
    ) -> None:
        """Use the ledger and the suffered-withholding read capabilities."""
        self._transactions = transaction_repository
        self._ports = retencion_soportada_ports

    def _payer_evidence(self, year: int) -> _PayerEvidenceRead:
        records = {
            _payer_key(record): record
            for record in self._ports.repository.load_records(year)
            if record.income_class is _CLASS
        }
        absences = self._ports.absences
        attested = absences is not None and any(
            item.active and item.income_class is _CLASS for item in absences.load_attestations(year)
        )
        return _PayerEvidenceRead(records=records, attested=attested)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve each family binding to its occurrences' total, or leave it open with the note that says why."""
        if not revision_declares_capital_mobiliario_position(context.revision):
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        try:
            transactions = self._transactions.load().transactions
            read = self._payer_evidence(context.period.filing_year)
            positions = profile_positions(context)
        except (RetencionSoportadaPersistenceError, ProfileAnswerTypeError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        with source_context_operation(context) as operation:
            end = context.period.end_date
            vocabulary = resolve_capital_mobiliario_concept_vocabulary(effective_date=end, authority=operation)
            rate = resolve_capital_mobiliario_withholding_rate(effective_date=end, authority=operation)
        join = join_capital_mobiliario_positions(
            positions, transactions.values(), vocabulary, start=context.period.start_date, end=end
        )
        computation = _compute(join, read, rate)
        opened = _open_bindings(context.revision, computation.findings)
        row_columns = _row_columns(context.revision)
        open_totals = {binding_id: found for binding_id, found in opened.items() if binding_id not in row_columns}
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=resolve_capital_mobiliario_position_binding_values(
                context.revision, computation.computed, excluded=frozenset(opened)
            ),
            row_binding_values=resolve_capital_mobiliario_row_values(
                context.revision, computation.computed, excluded=frozenset(opened)
            ),
            unresolved_binding_ids=tuple(open_totals),
            diagnostics=self._diagnostics(context.revision, open_totals),
            provenance=self._provenance(join, computation, read),
            source_transaction_ids=join.source_transaction_ids,
        )

    def _diagnostics(
        self, revision: ModeloRevision, opened: Mapping[BindingId, Sequence[_Finding]]
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return tuple(
            CalculationSourceDiagnostic(
                reason="unresolved_binding",
                source_kind=_SOURCE_KIND.value,
                binding_source=_SOURCE_KIND,
                resolver_id=self.resolver_id,
                binding_id=binding_id,
                casilla_id=sole_bound_casilla(revision, binding_id),
                message=(
                    f"binding {binding_id!r} stays unresolved: {finding.sentence.value.replace('_', ' ')}; "
                    "a capital-mobiliario figure is never guessed"
                ),
                remedy=finding.remedy,
                fact=CalculationNoteFact(
                    sentence=finding.sentence,
                    values=tuple(sorted((name, str(value)) for name, value in finding.values.items())),
                    row_refs=tuple(finding.rows),
                ),
            )
            for binding_id, findings in opened.items()
            for finding in findings
        )

    def _provenance(
        self, join: CapitalMobiliarioJoin, computation: _Computation, read: _PayerEvidenceRead
    ) -> tuple[CalculationSourceProvenance, ...]:
        computed_keys = {(item.position_ref, item.detail_record) for item in computation.computed}
        rows = tuple(
            self._node(
                f"{CAPITAL_MOBILIARIO_POSITION_REF_PREFIX}{position_ref}:{detail_record}",
                TerminalOriginClass.LEDGER_AGGREGATE,
                None,
            )
            for position_ref, detail_record in sorted(computed_keys)
        )
        payers = tuple(self._payer_node(key, read) for key in sorted(computation.payers_used))
        return (*rows, *payers)

    def _payer_node(self, key: str, read: _PayerEvidenceRead) -> CalculationSourceProvenance:
        record = read.records.get(key)
        if record is None:
            return self._node(
                f"{CAPITAL_MOBILIARIO_PAYER_REF_PREFIX}absence:{_CLASS.value}", TerminalOriginClass.OPERATOR_INPUT, None
            )
        origin = (
            TerminalOriginClass.PAYER_CERTIFICATE
            if record.origin is RetencionSoportadaOrigen.PAYER_CERTIFICATE
            else TerminalOriginClass.OPERATOR_INPUT
        )
        return self._node(
            f"{CAPITAL_MOBILIARIO_PAYER_REF_PREFIX}{record.payer_ref}", origin, record.evidence_fingerprint
        )

    def _node(
        self, source_ref: str, origin: TerminalOriginClass, fingerprint: str | None
    ) -> CalculationSourceProvenance:
        return CalculationSourceProvenance(
            resolver_id=self.resolver_id,
            resolved_binding_source=_SOURCE_KIND,
            contributor_source_kind=_SOURCE_KIND.value,
            contributor_binding_source=_SOURCE_KIND,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=source_ref,
            parent_source_ref=None,
            fingerprint=fingerprint,
            terminal_origin=origin,
        )


def profile_positions(context: CalculationSourceContext) -> tuple[PosicionRecord, ...]:
    """Return the profile's positions as the period's end reads them; none without a profile.

    Raises:
        ProfileAnswerTypeError: When a stored position's facts do not cohere.
    """
    if context.profile is None:
        return ()
    from ..user_profile.profile_read_recorder import profile_view_under
    from ..user_profile.projections import record_to_path_values

    values = record_to_path_values(context.profile.record, as_of=context.period.end_date)
    return posiciones_from_facts(profile_view_under(values, f"{POSICION_SECTION}."))
