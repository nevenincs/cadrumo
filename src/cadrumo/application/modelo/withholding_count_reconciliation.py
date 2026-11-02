"""Reconcile an annual summary's perceptors with its periodic return's declared counts.

The periodic return's "N.º perceptores" boxes count the persons and attributing
entities the declarant paid in that return's own period (AEAT, Modelo 111
instructions, "Casillas 01 y 07"). The annual summary carries each perceptor's
NIF on its type-2 records (Orden EHA/3127/2009 art. 2.1 and Annex; RIRPF art.
108.2), and those records split by clave, subclave, accrual year and contract.

Those definitions fix one comparison and rule out two tempting ones:

- Quarters are not summed. One employee paid all year is one perceptor in each
  of four returns and one perceptor on the summary, which is correct.
- Type-2 records are not perceptors. One person paid under three claves holds
  three records, so a record count cannot satisfy a count of persons. The
  comparison reads distinct perceptor identities.
- The check runs one way. The summary also declares exempt income, which no
  periodic box counts, so a summary naming more perceptors than a box proves
  nothing.

So the rule is a floor: no single box in any observed quarter can exceed the
summary's distinct perceptors, because each person that box counted must appear
there. Boxes are not added together, since one person paid both employment and
activity income sits in two boxes.

A quarter with no observation stays unknown and is reported as not cross-checked,
never as a count of zero. Monthly filers never reach this comparison: calculating
their summary is already refused, and their monthly coordinates are not quarters.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.casilla_id import CasillaId
from ...core.operator_action_enums import ActionEvidenceProvenance
from ...core.period import Period
from ...domain.calculations.registry.binding_selector_utils import provider_member
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.retenciones_bindings import (
    RetencionesAggregationFact,
    RetencionesAggregationProvider,
)
from ...domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ..aggregation.withholding_filing_cadence import QUARTERLY_WITHHOLDING_PERIODS
from ..aggregation.withholding_modelo_routing import annual_withholding_composition
from ..aggregation.withholding_source import withholding_binding_grounding
from .finding_message_text import NO_PERIODS_FACT, PERIOD_LIST_SEPARATOR
from .verification_preconditions import build_verification_precondition_failure

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.calculations.registry.ids import LegalRefId, SourceRefId
    from ...domain.calculations.registry.schema import ModeloRevision, RegistrySnapshot
    from ...domain.modelos.work_unit import WorkUnit
    from ..aggregation.percepciones_observations_repository import PercepcionObservationRepository
    from ..calculations.observations_repository import CalculationObservationRepositoryProtocol
    from .preconditions import ModeloPreconditionFailure


@dataclass(frozen=True, slots=True)
class WithholdingCountExcess:
    """One periodic box declaring more persons than the annual summary names."""

    period: str
    casilla_id: CasillaId
    declared_perceptors: Decimal


@dataclass(frozen=True, slots=True)
class WithholdingCountReconciliation:
    """The outcome of comparing one annual summary with its periodic counts.

    ``checked_periods`` holds an observation; ``unchecked_periods`` does not, and
    says nothing about how many persons that quarter paid.
    """

    modelo: str
    filing_year: int
    source_modelo: str
    summary_perceptors: int
    checked_periods: tuple[str, ...]
    unchecked_periods: tuple[str, ...]
    excesses: tuple[WithholdingCountExcess, ...]
    legal_refs: tuple[LegalRefId, ...]
    source_refs: tuple[SourceRefId, ...]


def _perceptor_count_casilla_ids(revision: ModeloRevision) -> tuple[CasillaId, ...]:
    """Return the casillas the periodic revision's own bindings declare as distinct-person counts."""
    selectors = (
        provider_member(binding, RetencionesAggregationProvider)
        for binding in revision.bindings
        if binding.source == BindingSourceKind.RETENCIONES_AGGREGATION
    )
    return tuple(
        selector.target_casilla_id
        for selector in selectors
        if selector.fact is RetencionesAggregationFact.PERCEPTOR_COUNT_DISTINCT
    )


def resolve_withholding_count_reconciliation(
    *,
    work_unit: WorkUnit,
    snapshot: RegistrySnapshot,
    observation_repository: CalculationObservationRepositoryProtocol,
    percepcion_repository: PercepcionObservationRepository,
    operation: PinnedAuthorityOperation,
) -> WithholdingCountReconciliation | None:
    """Compare the periodic boxes with the summary's distinct perceptors, or ``None``.

    ``None`` when the modelo's composition folds no periodic percepciones, so the
    registry routing decides which summaries this reaches.
    """
    modelo = str(work_unit.modelo)
    source_modelo = annual_withholding_composition(modelo).periodic_percepciones
    if source_modelo is None:
        return None
    filing_year = work_unit.filing_year
    summary_perceptors = len(
        {
            row.perceptor_tax_id
            for row in percepcion_repository.load_annual_source_observations(source_modelo.value, filing_year)
        }
    )
    legal_refs, source_refs = withholding_binding_grounding(snapshot.revision)
    checked: list[str] = []
    unchecked: list[str] = []
    excesses: list[WithholdingCountExcess] = []
    for period_code in QUARTERLY_WITHHOLDING_PERIODS:
        payload = observation_repository.load_observation(
            source_modelo.value,
            Period.from_year_and_code(filing_year, period_code),
        )
        if payload is None:
            unchecked.append(period_code)
            continue
        try:
            periodic = operation.snapshot(source_modelo, filing_year=filing_year, period=period_code).revision
        except (RegistrySnapshotError, RegistryValidationError):
            unchecked.append(period_code)
            continue
        checked.append(period_code)
        values = payload.observation.casilla_values
        for casilla_id in _perceptor_count_casilla_ids(periodic):
            declared = values.get(casilla_id)
            if declared is not None and declared > summary_perceptors:
                excesses.append(WithholdingCountExcess(period_code, casilla_id, declared))
        periodic_legal_refs, periodic_source_refs = _count_binding_grounding(periodic)
        legal_refs = tuple(sorted({*legal_refs, *periodic_legal_refs}))
        source_refs = tuple(sorted({*source_refs, *periodic_source_refs}))
    return WithholdingCountReconciliation(
        modelo=modelo,
        filing_year=filing_year,
        source_modelo=source_modelo.value,
        summary_perceptors=summary_perceptors,
        checked_periods=tuple(checked),
        unchecked_periods=tuple(unchecked),
        excesses=tuple(excesses),
        legal_refs=legal_refs,
        source_refs=source_refs,
    )


def _count_binding_grounding(revision: ModeloRevision) -> tuple[tuple[LegalRefId, ...], tuple[SourceRefId, ...]]:
    """Return the references the periodic revision attaches to its count bindings."""
    count_ids = set(_perceptor_count_casilla_ids(revision))
    bindings = tuple(
        binding
        for binding in revision.bindings
        if binding.source == BindingSourceKind.RETENCIONES_AGGREGATION
        and provider_member(binding, RetencionesAggregationProvider).target_casilla_id in count_ids
    )
    return (
        tuple(ref for binding in bindings for ref in binding.legal_refs),
        tuple(citation.source_ref for binding in bindings for citation in binding.source_citations),
    )


def _joined(values: Sequence[str]) -> str:
    return PERIOD_LIST_SEPARATOR.join(values) if values else NO_PERIODS_FACT


def append_withholding_count_reconciliation_findings(
    *,
    work_unit: WorkUnit,
    target_calculation_revision_id: str,
    target_work_unit_id: str,
    snapshot: RegistrySnapshot,
    observation_repository: CalculationObservationRepositoryProtocol,
    percepcion_repository: PercepcionObservationRepository,
    operation: PinnedAuthorityOperation,
    findings: list[ModeloVerificationFinding],
    failures_by_finding_id: dict[int, ModeloPreconditionFailure],
) -> None:
    """Append one blocking finding per excess box and one note for unchecked quarters."""
    reconciliation = resolve_withholding_count_reconciliation(
        work_unit=work_unit,
        snapshot=snapshot,
        observation_repository=observation_repository,
        percepcion_repository=percepcion_repository,
        operation=operation,
    )
    if reconciliation is None:
        return
    facts: dict[str, str | int] = {
        "modelo": reconciliation.modelo,
        "filing_year": reconciliation.filing_year,
        "source_modelo": reconciliation.source_modelo,
        "summary_perceptors": reconciliation.summary_perceptors,
        "checked_periods": _joined(reconciliation.checked_periods),
        "unchecked_periods": _joined(reconciliation.unchecked_periods),
    }
    for excess in reconciliation.excesses:
        finding = ModeloVerificationFinding(
            kind=ModeloVerificationFindingKind.BLOCKING_RULE,
            severity=ModeloVerificationFindingSeverity.BLOCKING,
            casilla_id=excess.casilla_id,
            message_locale_key="application.modelo.findings.withholding_count_exceeds_summary_perceptors",
            message_facts={
                "modelo": reconciliation.modelo,
                "filing_year": reconciliation.filing_year,
                "source_modelo": reconciliation.source_modelo,
                "summary_perceptors": reconciliation.summary_perceptors,
                "checked_periods": _joined(reconciliation.checked_periods),
                "unchecked_periods": _joined(reconciliation.unchecked_periods),
                "period": excess.period,
                "casilla_id": str(excess.casilla_id),
                "declared_perceptors": str(excess.declared_perceptors),
            },
            legal_refs=reconciliation.legal_refs,
            source_refs=reconciliation.source_refs,
        )
        findings.append(finding)
        failures_by_finding_id[id(finding)] = build_verification_precondition_failure(
            calculation_revision_id=target_calculation_revision_id,
            work_unit_id=target_work_unit_id,
            condition_id="modelo.work.verify.withholding_count.reconciled",
            scenario_id="modelo.work.verify.withholding_count.exceeded",
            evidence_id="modelo.work.verify.withholding_count",
            evidence_values={
                "modelo": reconciliation.modelo,
                "year": reconciliation.filing_year,
                "source_modelo": reconciliation.source_modelo,
                "period": excess.period,
                "casilla_id": str(excess.casilla_id),
                "declared_perceptors": str(excess.declared_perceptors),
                "summary_perceptors": reconciliation.summary_perceptors,
            },
            provenance=ActionEvidenceProvenance.PERSISTED_STATE,
        )
    if reconciliation.unchecked_periods:
        findings.append(
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.ADVISORY,
                severity=ModeloVerificationFindingSeverity.WARNING,
                message_locale_key="application.modelo.findings.withholding_count_not_cross_checked",
                message_facts=facts,
                legal_refs=reconciliation.legal_refs,
                source_refs=reconciliation.source_refs,
            )
        )


__all__ = [
    "WithholdingCountExcess",
    "WithholdingCountReconciliation",
    "append_withholding_count_reconciliation_findings",
    "resolve_withholding_count_reconciliation",
]
