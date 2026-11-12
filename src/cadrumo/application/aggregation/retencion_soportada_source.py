"""Source mesh resolver for withholding the taxpayer suffered, per payer and income class.

Each state stays apart, and none of them is invented here:

* **absent** -- the revision declares no member of the family. The resolver
  reads nothing and returns an empty resolution, which differs from reading an
  empty store.
* **recorded** -- records exist, and the binding takes the sum of the drawn
  quantity over every payer of its class. A record whose figures are zero is
  present and yields a proven zero.
* **attested absent** -- no record exists and the operator's active absence
  attestation covers the class: a proven zero resting on operator input, never
  on a payer's statement.
* **declared absent** -- no record exists and the profile's income categories
  for the ejercicio positively exclude the class's income: a proven zero
  resting on that profile fact.
* **missing** -- no record and no attestation, while the profile declares the
  class's income or says nothing readable about it. The binding receives no
  value and is reported unresolved with a typed finding naming the class and
  its two remedies, so the casilla blocks instead of reading as zero.
* **contradicted** -- records exist beside an active attestation that the class
  had none. Neither is taken: the binding is unresolved with a typed finding,
  and blocks until the operator removes one of them.

Every record of the ejercicio is read whenever the family is declared. A record
whose class no binding of the revision consumes is reported unrouted, which
blocks, so no payer's withholding is dropped without a word.

The resolver reads only its own store; no withholding-agent store or source kind
reaches it. Each contributing record is one primary provenance node named by
its keyed ``payer_ref``, never by the payer's tax identifier;
:class:`ModeloRevision`, the registry revision a modelo is calculated against.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.retencion_soportada import RetencionSoportadaCantidad, RetencionSoportadaClase
from ...domain.calculations.registry.binding_targets import sole_bound_casilla
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.credit_reconciliation import RetencionSoportadaCrossCheck
from ...domain.calculations.registry.retencion_soportada_bindings import (
    RETENCION_SOPORTADA_INCOME_ROLES,
    retencion_soportada_bindings,
    revision_declares_retencion_soportada,
)
from ...domain.calculations.registry.runtime_graph import expression_binding_refs
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ...domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ...domain.renta.retencion_soportada_applicability import (
    RetencionSoportadaApplicability,
    retencion_soportada_applicability,
)
from .modelo_bindings_support import STORAGE_DEGRADATION_ERRORS, empty_source_resolution
from .retencion_soportada_absence_repository import retencion_soportada_absence_key
from .retencion_soportada_repository import (
    RetencionSoportadaPersistenceError,
    RetencionSoportadaPorts,
    retencion_soportada_record_key,
)
from .source_mesh import (
    CalculationSourceContext,
    CalculationSourceDiagnostic,
    CalculationSourceProvenance,
    CalculationSourceResolution,
)
from .source_resolution_operations import source_context_operation, storage_degradation_resolution

if TYPE_CHECKING:
    from datetime import date

    from ...core.casilla_id import CasillaId
    from ...core.period import Period
    from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "IRPF_INCOME_CATEGORIES_PROFILE_PATH",
    "RETENCION_SOPORTADA_SOURCE_REF_PREFIX",
    "RetencionSoportadaClassState",
    "RetencionSoportadaSourceResolver",
    "recorded_income_classes",
]

RETENCION_SOPORTADA_SOURCE_REF_PREFIX: Final[str] = "retencion-soportada:"
"""The provenance reference family of one payer record or attestation; its subject is the row's object key."""

IRPF_INCOME_CATEGORIES_PROFILE_PATH: Final[str] = "taxpayer_type.irpf_income_categories"
"""The profile fact whose categories decide whether a class's income exists in the ejercicio."""

_SOURCE_KIND: Final = BindingSourceKind.RETENCION_SOPORTADA

_TERMINAL_ORIGIN_BY_RECORD_ORIGIN: Final[dict[RetencionSoportadaOrigen, TerminalOriginClass]] = {
    RetencionSoportadaOrigen.PAYER_CERTIFICATE: TerminalOriginClass.PAYER_CERTIFICATE,
    RetencionSoportadaOrigen.OPERATOR_DECLARATION: TerminalOriginClass.OPERATOR_INPUT,
}

_EVIDENCE_REMEDY: Final[str] = (
    "Record each payer's certificate with app ledger retencion-soportada record, or, if no payer withheld on "
    "this income class, attest it with app ledger retencion-soportada attest-absence."
)
_CONTRADICTION_REMEDY: Final[str] = (
    "Remove the payer records with app ledger retencion-soportada remove, or withdraw the attestation with "
    "app ledger retencion-soportada withdraw-absence."
)


_INCOME_RECORD_REMEDY: Final[str] = (
    "Withdraw the attestation with app ledger retencion-soportada withdraw-absence, then record each payer's "
    "certificate with app ledger retencion-soportada record and --origin operator_declaration."
)
_FIGURE_MISSING_REMEDY: Final[str] = (
    "Replace the payer record with the certificate's figures using app ledger retencion-soportada record."
)


class RetencionSoportadaClassState(StrEnum):
    """How one bound income class resolved on one calculation."""

    RECORDED = "recorded"
    ATTESTED_ABSENT = "attested_absent"
    DECLARED_ABSENT = "declared_absent"
    MISSING = "missing"
    CONTRADICTED = "contradicted"
    MISSING_INCOME_RECORD = "missing_income_record"
    """An attestation covers the class, but an income binding needs a record that states the income."""
    FIGURE_MISSING = "figure_missing"
    """Records exist, but one lacks a figure the binding draws (a payload written before the figure existed)."""


_PROVEN_ZERO_STATES: Final = frozenset(
    {RetencionSoportadaClassState.ATTESTED_ABSENT, RetencionSoportadaClassState.DECLARED_ABSENT},
)


def recorded_income_classes(source_refs: Iterable[str]) -> frozenset[RetencionSoportadaClase]:
    """Return the income classes that a payer record, not an attestation, contributed to a calculation.

    ``source_refs`` are the provenance references of a calculation revision. A record's reference is
    ``retencion-soportada:{ejercicio}:{income_class}:{payer_ref}``; an attestation's carries the word
    ``absence`` where the ejercicio stands, so it names no class here.
    """
    classes: set[RetencionSoportadaClase] = set()
    for ref in source_refs:
        if not ref.startswith(RETENCION_SOPORTADA_SOURCE_REF_PREFIX):
            continue
        parts = ref.removeprefix(RETENCION_SOPORTADA_SOURCE_REF_PREFIX).split(":")
        if len(parts) == 3 and parts[0].isdigit():
            try:
                classes.add(RetencionSoportadaClase(parts[1]))
            except ValueError:
                continue
    return frozenset(classes)


def _source_ref(record: RetencionSoportadaRecord) -> str:
    return f"{RETENCION_SOPORTADA_SOURCE_REF_PREFIX}{retencion_soportada_record_key(record.identity)}"


def _attestation_source_ref(attestation: RetencionSoportadaAbsence) -> str:
    return f"{RETENCION_SOPORTADA_SOURCE_REF_PREFIX}{retencion_soportada_absence_key(attestation.identity)}"


def _declared_categories(context: CalculationSourceContext) -> frozenset[str] | None:
    """Return the profile's income categories in force at the period's end, or ``None`` when it declares none."""
    if context.profile is None:
        return None
    from ..user_profile.projections import record_to_path_values

    raw = record_to_path_values(context.profile.record, as_of=context.period.end_date).get(
        IRPF_INCOME_CATEGORIES_PROFILE_PATH,
    )
    if raw is None:
        return None
    return frozenset(token.strip() for token in raw.split(",") if token.strip()) or None


_ACTIVITY_SECTION: Final[str] = "activities"
_IAE_EPIGRAPH_FIELD: Final[str] = "iae_epigraph"


def declared_activity_epigraphs(context: CalculationSourceContext) -> tuple[str | None, ...] | None:
    """Return each declared activity's IAE epigraph in force at the period's end, ``None`` for one without.

    Rows are the profile's own activity rows, read by the shared section-row
    grouping: the setup wizard's unindexed row and every indexed row, the first
    of which the row mutation stores at index 0. ``None`` overall when the
    profile cannot be read; an empty tuple when it declares no activity.
    """
    if context.profile is None:
        return None
    from ..user_profile.completeness import profile_section_rows
    from ..user_profile.projections import record_to_path_values

    values = record_to_path_values(context.profile.record, as_of=context.period.end_date)
    epigraphs: list[str | None] = []
    for row in profile_section_rows(_ACTIVITY_SECTION, values):
        path = ".".join(part for part in (_ACTIVITY_SECTION, row, _IAE_EPIGRAPH_FIELD) if part)
        epigraph = (values.get(path) or "").strip()
        epigraphs.append(epigraph or None)
    return tuple(epigraphs)


def _class_state(
    income_class: RetencionSoportadaClase,
    class_records: Sequence[RetencionSoportadaRecord],
    attestation: RetencionSoportadaAbsence | None,
    declared: frozenset[str] | None,
    activity_epigraphs: tuple[str | None, ...] | None,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> RetencionSoportadaClassState:
    if class_records:
        if attestation is not None:
            return RetencionSoportadaClassState.CONTRADICTED
        return RetencionSoportadaClassState.RECORDED
    if attestation is not None:
        return RetencionSoportadaClassState.ATTESTED_ABSENT
    applicability = retencion_soportada_applicability(
        income_class, declared, activity_epigraphs, effective_date=effective_date, authority=authority
    )
    if applicability is RetencionSoportadaApplicability.DECLARED_ABSENT:
        return RetencionSoportadaClassState.DECLARED_ABSENT
    return RetencionSoportadaClassState.MISSING


def _refined_state(
    state: RetencionSoportadaClassState,
    income_class: RetencionSoportadaClase,
    quantity: RetencionSoportadaCantidad,
    class_records: Sequence[RetencionSoportadaRecord],
) -> RetencionSoportadaClassState:
    """Narrow a class state by the quantity drawn: a figure a record lacks, or income an attestation cannot state."""
    if state is RetencionSoportadaClassState.RECORDED and not all(record.states(quantity) for record in class_records):
        return RetencionSoportadaClassState.FIGURE_MISSING
    if (
        state is RetencionSoportadaClassState.ATTESTED_ABSENT
        and (income_class, quantity) in RETENCION_SOPORTADA_INCOME_ROLES
    ):
        # An attestation says no payer withheld, never how much income there was.
        return RetencionSoportadaClassState.MISSING_INCOME_RECORD
    return state


def _credited_casilla(revision: ModeloRevision, binding_id: BindingId) -> CasillaId | None:
    """Return the one casilla a family binding credits: the box it is bound to, else the one formula reading it.

    A binding read as a formula operand populates no box of its own, so a note that it is
    unresolved names the computed credit box it leaves unresolved, and reaches the gate there.
    """
    bound = sole_bound_casilla(revision, binding_id)
    if bound is not None:
        return bound
    readers = {
        formula.target_casilla_id
        for formula in revision.formulas
        if binding_id in expression_binding_refs(formula.expression)
    }
    return next(iter(readers)) if len(readers) == 1 else None


def _cross_checked_classes(revision: ModeloRevision) -> set[RetencionSoportadaClase]:
    """Return the income classes the revision's credit reconciliation compares a credit with."""
    return {
        cross_check.income_class
        for entry in revision.credit_reconciliation
        for cross_check in entry.cross_checks
        if isinstance(cross_check, RetencionSoportadaCrossCheck)
    }


def _records_by_class(
    records: Sequence[RetencionSoportadaRecord],
) -> defaultdict[RetencionSoportadaClase, list[RetencionSoportadaRecord]]:
    by_class: defaultdict[RetencionSoportadaClase, list[RetencionSoportadaRecord]] = defaultdict(list)
    for record in records:
        by_class[record.income_class].append(record)
    return by_class


class RetencionSoportadaSourceResolver:
    """Resolve the family's bindings from the per-payer records, attestations and the profile's categories."""

    resolver_id: ClassVar[str] = "retencion_soportada"
    owned_sources: ClassVar[tuple[BindingSourceKind, ...]] = (BindingSourceKind.RETENCION_SOPORTADA,)

    def __init__(self, *, ports: RetencionSoportadaPorts) -> None:
        """Use the required suffered-withholding read capability."""
        self._ports = ports

    def load_calculation_records(
        self,
        *,
        period: Period,
        revision: ModeloRevision,
    ) -> tuple[RetencionSoportadaRecord, ...] | None:
        """Return every stored record of the period's ejercicio, or ``None`` when the family is absent.

        ``None`` means the revision declares no member of the family, so the
        calculation reads nothing from this store; an empty tuple means it read
        the store and found no record.

        ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
        """
        if not revision_declares_retencion_soportada(revision):
            return None
        return self._ports.repository.load_records(period.filing_year)

    def load_calculation_attestations(
        self,
        *,
        period: Period,
        revision: ModeloRevision,
    ) -> tuple[RetencionSoportadaAbsence, ...]:
        """Return the active absence attestations of the period's ejercicio; none when the family is absent.

        ``revision`` is the :class:`ModeloRevision`, the registry revision a modelo is calculated against.
        """
        absences = self._ports.absences
        if absences is None or not revision_declares_retencion_soportada(revision):
            return ()
        return tuple(item for item in absences.load_attestations(period.filing_year) if item.active)

    def resolve(self, context: CalculationSourceContext) -> CalculationSourceResolution:
        """Resolve each family binding to its class total or a proven zero, or leave it unresolved."""
        try:
            records = self.load_calculation_records(period=context.period, revision=context.revision)
            attestations = self.load_calculation_attestations(period=context.period, revision=context.revision)
        except (RetencionSoportadaPersistenceError, *STORAGE_DEGRADATION_ERRORS) as exc:
            return storage_degradation_resolution(
                resolver_id=self.resolver_id,
                owned_sources=self.owned_sources,
                source_kinds=self.owned_sources,
                error=exc,
            )
        if records is None:
            return empty_source_resolution(self.resolver_id, self.owned_sources)
        by_class = _records_by_class(records)
        attested = {item.income_class: item for item in attestations}
        declared = _declared_categories(context)
        activity_epigraphs = declared_activity_epigraphs(context)
        binding_values: dict[BindingId, Decimal] = {}
        unresolved: list[BindingId] = []
        diagnostics: list[CalculationSourceDiagnostic] = []
        zero_provenance: dict[RetencionSoportadaClase, CalculationSourceProvenance] = {}
        consumed: set[RetencionSoportadaClase] = set()
        with source_context_operation(context) as operation:
            for binding, provider in retencion_soportada_bindings(context.revision):
                income_class = provider.income_class
                consumed.add(income_class)
                class_records = by_class.get(income_class, [])
                attestation = attested.get(income_class)
                state = _class_state(
                    income_class,
                    class_records,
                    attestation,
                    declared,
                    activity_epigraphs,
                    effective_date=context.period.end_date,
                    authority=operation,
                )
                state = _refined_state(state, income_class, provider.quantity, class_records)
                if state is RetencionSoportadaClassState.RECORDED:
                    binding_values[binding.id] = sum(
                        (record.quantity(provider.quantity) for record in class_records),
                        Decimal("0"),
                    )
                elif state in _PROVEN_ZERO_STATES:
                    binding_values[binding.id] = Decimal("0.00")
                    zero_provenance.setdefault(income_class, self._zero_provenance(context, income_class, attestation))
                else:
                    # Named unresolved here as well as in the note, so a formula reading the binding as an
                    # operand leaves its own box unresolved instead of failing on a missing value.
                    unresolved.append(binding.id)
                    diagnostics.append(self._unresolved_diagnostic(context.revision, binding.id, income_class, state))
        # A class a credit casilla is cross-checked against is read by that comparison, so its
        # records are not unrouted even where no binding credits them.
        compared = consumed | _cross_checked_classes(context.revision)
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            unresolved_binding_ids=tuple(unresolved),
            diagnostics=(*diagnostics, *self._unrouted_diagnostics(context.revision, records, compared)),
            provenance=self._resolution_provenance(records, consumed, zero_provenance),
        )

    def _resolution_provenance(
        self,
        records: tuple[RetencionSoportadaRecord, ...],
        consumed: set[RetencionSoportadaClase],
        zero_provenance: dict[RetencionSoportadaClase, CalculationSourceProvenance],
    ) -> tuple[CalculationSourceProvenance, ...]:
        contributing = tuple(record for record in records if record.income_class in consumed)
        return (*(self._provenance(record) for record in contributing), *zero_provenance.values())

    def _unresolved_diagnostic(
        self,
        revision: ModeloRevision,
        binding_id: BindingId,
        income_class: RetencionSoportadaClase,
        state: RetencionSoportadaClassState,
    ) -> CalculationSourceDiagnostic:
        if state is RetencionSoportadaClassState.MISSING_INCOME_RECORD:
            sentence = CalculationNoteSentence.RETENCION_SOPORTADA_INCOME_RECORD_REQUIRED
            message = (
                f"income class {income_class.value!r} is attested as withheld by no payer, which says nothing "
                "about the amount of its income; the income needs a payer record"
            )
            remedy = _INCOME_RECORD_REMEDY
        elif state is RetencionSoportadaClassState.FIGURE_MISSING:
            sentence = CalculationNoteSentence.RETENCION_SOPORTADA_RECORD_FIGURE_MISSING
            message = (
                f"a payer record of income class {income_class.value!r} was stored before the certificate figure "
                "this binding draws existed, and does not state it"
            )
            remedy = _FIGURE_MISSING_REMEDY
        elif state is RetencionSoportadaClassState.CONTRADICTED:
            sentence = CalculationNoteSentence.RETENCION_SOPORTADA_ABSENCE_CONTRADICTED
            message = (
                f"income class {income_class.value!r} holds payer records and an attestation that no payer "
                "withheld on it; neither is credited until one of them is removed"
            )
            remedy = _CONTRADICTION_REMEDY
        else:
            sentence = CalculationNoteSentence.RETENCION_SOPORTADA_EVIDENCE_REQUIRED
            message = (
                f"income class {income_class.value!r} has no payer record and no absence attestation for this "
                "ejercicio, and the profile does not declare its income absent; a missing record is never read "
                "as zero"
            )
            remedy = _EVIDENCE_REMEDY
        return CalculationSourceDiagnostic(
            reason="unresolved_binding",
            source_kind=_SOURCE_KIND.value,
            resolver_id=self.resolver_id,
            binding_id=binding_id,
            casilla_id=_credited_casilla(revision, binding_id),
            message=message,
            remedy=remedy,
            fact=CalculationNoteFact.of(sentence, income_class=income_class.value),
        )

    def _unrouted_diagnostics(
        self,
        revision: ModeloRevision,
        records: tuple[RetencionSoportadaRecord, ...],
        consumed: set[RetencionSoportadaClase],
    ) -> tuple[CalculationSourceDiagnostic, ...]:
        return tuple(
            CalculationSourceDiagnostic(
                reason="unrouted_observation",
                source_kind=_SOURCE_KIND.value,
                resolver_id=self.resolver_id,
                source_ref=_source_ref(record),
                message=(
                    f"a suffered-withholding record of income class {record.income_class.value!r} is consumed by "
                    f"no binding on revision {revision.id!r}; its withholding is not credited on this calculation"
                ),
            )
            for record in records
            if record.income_class not in consumed
        )

    def _provenance(self, record: RetencionSoportadaRecord) -> CalculationSourceProvenance:
        return CalculationSourceProvenance(
            resolver_id=self.resolver_id,
            resolved_binding_source=_SOURCE_KIND,
            contributor_source_kind=_SOURCE_KIND.value,
            contributor_binding_source=_SOURCE_KIND,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=_source_ref(record),
            parent_source_ref=None,
            fingerprint=record.evidence_fingerprint,
            terminal_origin=_TERMINAL_ORIGIN_BY_RECORD_ORIGIN[record.origin],
        )

    def _zero_provenance(
        self,
        context: CalculationSourceContext,
        income_class: RetencionSoportadaClase,
        attestation: RetencionSoportadaAbsence | None,
    ) -> CalculationSourceProvenance:
        """Name what a proven zero rests on: the operator's attestation, or the profile's declared categories."""
        if attestation is not None:
            source_ref = _attestation_source_ref(attestation)
            terminal_origin = TerminalOriginClass.OPERATOR_INPUT
        else:
            source_ref = (
                f"profile:{context.bucket_id}:{IRPF_INCOME_CATEGORIES_PROFILE_PATH}:"
                f"{context.period.filing_year}:{income_class.value}"
            )
            terminal_origin = TerminalOriginClass.PROFILE_FIELD
        return CalculationSourceProvenance(
            resolver_id=self.resolver_id,
            resolved_binding_source=_SOURCE_KIND,
            contributor_source_kind=_SOURCE_KIND.value,
            contributor_binding_source=_SOURCE_KIND,
            lineage_role=CalculationSourceLineageRole.PRIMARY,
            source_ref=source_ref,
            parent_source_ref=None,
            fingerprint=None,
            terminal_origin=terminal_origin,
        )
