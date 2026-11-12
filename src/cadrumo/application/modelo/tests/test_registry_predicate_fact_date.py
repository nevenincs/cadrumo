"""Registry predicates read the facts they decide at the work unit's own period date, never at the run date."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ....core.time.clock import frozen_clock
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ....domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ....domain.calculations.registry.schema_references import TemporalSupportEnvelope
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.contribuyente.renta_codes import FiscalResidency
from ....domain.deadlines.models import TaxpayerProfile
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.verification_report import ModeloVerificationFinding
from ....domain.modelos.work_unit import WorkUnit
from ..preconditions import ModeloPreconditionFailure
from ..verification_revision_findings import append_registry_predicate_findings

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_REPRESENTANTE_PREDICATE_ID = "m210-representante-fiscal-required"
_RESIDENCY_FACTS = frozenset({"renta-fiscal-residency-vocabulary", "eu-eea-country-membership"})
"""The facts the TRLIRNR art. 10 filter decides with: the residency's regime and EU/EEA membership."""


class _DateRecordingSource:
    """Delegate every governed-fact read to the pinned operation, keeping each fact and the date it asked for."""

    def __init__(self, inner: PinnedAuthorityOperation) -> None:
        self._inner = inner
        self.asked: list[tuple[str, date]] = []

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        self.asked.append((query.fact_id, query.effective_date))
        return self._inner.resolve_governed_fact(query)

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        return self._inner.supported_filing_years()


def _non_eea_irnr_profile_without_representante() -> TaxpayerProfile:
    return TaxpayerProfile.model_construct(
        tax_id="X0001500M",
        fiscal_residency=FiscalResidency.from_registry("non_resident_irnr"),
        country_of_fiscal_residence="AR",
        representante_fiscal_nif=None,
    )


@pytest.mark.parametrize(
    ("period_code", "expected_fact_date"),
    [
        # A quarter-spanning unit is judged at its own period end.
        ("1T", date(_YEAR, 3, 31)),
        # An annual unit and a Modelo 210 income unit are judged at 31 December,
        # the calculation date the formula runtime uses for the same unit.
        ("0A", date(_YEAR, 12, 31)),
        ("EVENT-1", date(_YEAR, 12, 31)),
    ],
)
def test_the_representative_predicate_reads_residency_at_the_unit_s_period_date(
    period_code: str,
    expected_fact_date: date,
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = published_snapshot("210", filing_year=_YEAR, period="EVENT-1")
    work_unit = WorkUnit.model_construct(
        work_unit_id="wu-210-fact-date",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, period_code),
    )
    target = CalculationRevision.model_construct(
        calculation_revision_id="calc-210-fact-date",
        work_unit_id="wu-210-fact-date",
        casilla_values={},
        input_values_by_casilla_id={},
    )
    findings: list[ModeloVerificationFinding] = []
    failures: dict[int, ModeloPreconditionFailure] = {}
    recorder = _DateRecordingSource(operation)
    run_date_outside_the_envelope = datetime(filing_year_envelope().floor - 3, 6, 15, 12, tzinfo=UTC)

    with frozen_clock(run_date_outside_the_envelope), validating_governed_facts(recorder):
        append_registry_predicate_findings(
            work_unit=work_unit,
            target=target,
            snapshot=snapshot,
            predicate_profile=_non_eea_irnr_profile_without_representante(),
            findings=findings,
            failures_by_finding_id=failures,
        )

    assert _REPRESENTANTE_PREDICATE_ID in {finding.message_facts.get("predicate_id") for finding in findings}
    residency_reads = {(fact_id, on) for fact_id, on in recorder.asked if fact_id in _RESIDENCY_FACTS}
    assert residency_reads == {(fact_id, expected_fact_date) for fact_id in _RESIDENCY_FACTS}
