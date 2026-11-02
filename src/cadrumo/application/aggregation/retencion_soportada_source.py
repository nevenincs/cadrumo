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
its keyed ``payer_ref``, never by the payer's tax identifier.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final

from ...core.aggregation import BindingSourceKind, CalculationSourceLineageRole
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.calculations.registry.binding_targets import sole_bound_casilla
from ...domain.calculations.registry.binding_terminal_origin import TerminalOriginClass
from ...domain.calculations.registry.retencion_soportada_bindings import (
    retencion_soportada_bindings,
    revision_declares_retencion_soportada,
)
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen, RetencionSoportadaRecord
from ...domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ...domain.renta.retencion_soportada_applicability import (
    RetencionSoportadaApplicability,
    retencion_soportada_applicability,
)
from ._modelo_bindings_support import STORAGE_DEGRADATION_ERRORS, empty_source_resolution
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
from .source_resolution_operations import storage_degradation_resolution

if TYPE_CHECKING:
    from ...core.period import Period
    from ...domain.calculations.registry.ids import BindingId
    from ...domain.calculations.registry.schema import ModeloRevision

__all__ = [
    "IRPF_INCOME_CATEGORIES_PROFILE_PATH",
    "RETENCION_SOPORTADA_SOURCE_REF_PREFIX",
    "RetencionSoportadaClassState",
    "RetencionSoportadaSourceResolver",
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


class RetencionSoportadaClassState(StrEnum):
    """How one bound income class resolved on one calculation."""

    RECORDED = "recorded"
    ATTESTED_ABSENT = "attested_absent"
    DECLARED_ABSENT = "declared_absent"
    MISSING = "missing"
    CONTRADICTED = "contradicted"


_PROVEN_ZERO_STATES: Final = frozenset(
    {RetencionSoportadaClassState.ATTESTED_ABSENT, RetencionSoportadaClassState.DECLARED_ABSENT},
)


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


def _class_state(
    income_class: RetencionSoportadaClase,
    class_records: Sequence[RetencionSoportadaRecord],
    attestation: RetencionSoportadaAbsence | None,
    declared: frozenset[str] | None,
) -> RetencionSoportadaClassState:
    if class_records:
        if attestation is not None:
            return RetencionSoportadaClassState.CONTRADICTED
        return RetencionSoportadaClassState.RECORDED
    if attestation is not None:
        return RetencionSoportadaClassState.ATTESTED_ABSENT
    if retencion_soportada_applicability(income_class, declared) is RetencionSoportadaApplicability.DECLARED_ABSENT:
        return RetencionSoportadaClassState.DECLARED_ABSENT
    return RetencionSoportadaClassState.MISSING


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
        """Return the active absence attestations of the period's ejercicio; none when the family is absent."""
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
        binding_values: dict[BindingId, Decimal] = {}
        diagnostics: list[CalculationSourceDiagnostic] = []
        zero_provenance: dict[RetencionSoportadaClase, CalculationSourceProvenance] = {}
        consumed: set[RetencionSoportadaClase] = set()
        for binding, provider in retencion_soportada_bindings(context.revision):
            income_class = provider.income_class
            consumed.add(income_class)
            class_records = by_class.get(income_class, [])
            attestation = attested.get(income_class)
            state = _class_state(income_class, class_records, attestation, declared)
            if state is RetencionSoportadaClassState.RECORDED:
                binding_values[binding.id] = sum(
                    (record.quantity(provider.quantity) for record in class_records),
                    Decimal("0"),
                )
            elif state in _PROVEN_ZERO_STATES:
                binding_values[binding.id] = Decimal("0.00")
                zero_provenance.setdefault(income_class, self._zero_provenance(context, income_class, attestation))
            else:
                diagnostics.append(self._unresolved_diagnostic(context.revision, binding.id, income_class, state))
        return CalculationSourceResolution(
            resolver_id=self.resolver_id,
            owned_sources=self.owned_sources,
            binding_values=binding_values,
            diagnostics=(*diagnostics, *self._unrouted_diagnostics(context.revision, records, consumed)),
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
        if state is RetencionSoportadaClassState.CONTRADICTED:
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
            casilla_id=sole_bound_casilla(revision, binding_id),
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
