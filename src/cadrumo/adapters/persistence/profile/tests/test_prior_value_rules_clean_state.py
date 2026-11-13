"""Clean-state verdicts for carries whose registry declares the prior-value rules.

The Modelo 200 preceding-period turnover carry declares both rules: a typed zero
proves nothing (a zero lowers the rate), and an earlier period that ended before
the activity began stays a dependency the filer must prove or state. Each case
runs the real evaluator over real profile stores, for every year of the support
envelope whose pinned edition declares the carry.
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from .....application.calculations.cross_period_clean_state import evaluate_cross_period_clean_state
from .....application.calculations.cross_period_models import (
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyEvidence,
    OperatorAttestedValue,
)
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.period import Period
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.modelos.calculation_revision_operator_layer import AttestedSource
from .....domain.modelos.work_unit import WorkUnitCatalogue
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..calculation_observations import CalculationObservationRepository
from ..justificante import JustificanteRepository
from ..modelos_calculation import CalculationRevisionCatalogueRepository
from ..modelos_filing import ModeloRecordCatalogueRepository
from ..modelos_verification_reports import VerificationReportCatalogueRepository
from .cross_period_clean_state_support import BUCKET_ID
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]

_MODELO = "200"
_PERIOD = "0A"
_GRADE = RegistryAuthorityGrade.CALCULATION


def _rule_carries(snapshot: RegistrySnapshot) -> tuple[str, ...]:
    return tuple(
        binding.id
        for binding in snapshot.revision.bindings
        if binding.zero_needs_attestation and binding.before_activity_unresolved
    )


def _years_declaring_the_rules() -> tuple[int, ...]:
    with bundled_indexed_authority().operation() as operation:
        return tuple(
            year
            for year in operation.supported_filing_years().years
            if _rule_carries(operation.snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=_GRADE))
        )


_YEARS = _years_declaring_the_rules()


def test_some_supported_year_declares_the_rules() -> None:
    assert _YEARS


def _evaluate(
    snapshot: RegistrySnapshot,
    *,
    zero_ids: frozenset[str] | None = None,
    attestations: dict[str, OperatorAttestedValue] | None = None,
    activity_start_offset_days: int | None = None,
) -> CrossPeriodCleanStateVerdict:
    prior_end = Period.from_year_and_code(snapshot.filing_year - 1, _PERIOD).end_date
    activity_start = None if activity_start_offset_days is None else prior_end + timedelta(activity_start_offset_days)
    return evaluate_cross_period_clean_state(
        snapshot,
        operation=published_authority_operation(),
        bucket_id=BUCKET_ID,
        observation_repository=CalculationObservationRepository(),
        filing_repository=ModeloRecordCatalogueRepository(),
        calculation_repository=CalculationRevisionCatalogueRepository(),
        verification_repository=VerificationReportCatalogueRepository(),
        justificante_repository=JustificanteRepository(),
        taxpayer_tax_id="B00015016",
        activity_start_date=activity_start,
        taxpayer_files_economic_activity=True,
        zero_value_previous_filing_binding_ids=zero_ids,
        operator_value_attestations=attestations,
        work_catalogue=WorkUnitCatalogue(),
    )


def _carry_evidence(verdict: CrossPeriodCleanStateVerdict, binding_id: str) -> CrossPeriodDependencyEvidence:
    return next(item for item in verdict.dependencies if binding_id in item.requirement.origin_ids)


def _stated(snapshot: RegistrySnapshot, binding_id: str, value: str) -> dict[str, OperatorAttestedValue]:
    source = AttestedSource(source_modelo=_MODELO, source_filing_year=snapshot.filing_year - 1, source_period=_PERIOD)
    return {binding_id: OperatorAttestedValue(binding_id=binding_id, value=value, sources=(source,))}


@pytest.mark.parametrize("year", _YEARS)
def test_a_typed_zero_does_not_verify_the_carry_clean(tmp_path: Path, year: int) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        snapshot = published_authority_operation().snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=_GRADE)
        (carry,) = _rule_carries(snapshot)
        evidence = _carry_evidence(_evaluate(snapshot, zero_ids=frozenset({carry})), carry)

    assert not evidence.clean
    assert evidence.blockers
    assert evidence.zero_value_previous_filing_advisory is False
    assert evidence.attestation_admitted


@pytest.mark.parametrize("year", _YEARS)
def test_an_attested_zero_verifies_the_carry_clean(tmp_path: Path, year: int) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        snapshot = published_authority_operation().snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=_GRADE)
        (carry,) = _rule_carries(snapshot)
        evidence = _carry_evidence(
            _evaluate(snapshot, zero_ids=frozenset({carry}), attestations=_stated(snapshot, carry, "0")), carry
        )

    assert evidence.clean
    assert [item.binding_id for item in evidence.operator_attested_absent_upstream] == [carry]


@pytest.mark.parametrize("year", _YEARS)
def test_a_period_before_the_activity_stays_a_dependency(tmp_path: Path, year: int) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        snapshot = published_authority_operation().snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=_GRADE)
        (carry,) = _rule_carries(snapshot)
        evidence = _carry_evidence(_evaluate(snapshot, activity_start_offset_days=1), carry)

    assert evidence.no_prior_obligation is None
    assert not evidence.clean
    assert evidence.attestation_admitted


@pytest.mark.parametrize("year", _YEARS)
def test_a_stated_first_period_figure_verifies_the_period_before_the_activity(tmp_path: Path, year: int) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=BUCKET_ID):
        snapshot = published_authority_operation().snapshot(_MODELO, filing_year=year, period=_PERIOD, grade=_GRADE)
        (carry,) = _rule_carries(snapshot)
        evidence = _carry_evidence(
            _evaluate(snapshot, activity_start_offset_days=1, attestations=_stated(snapshot, carry, "640000.00")),
            carry,
        )

    assert evidence.no_prior_obligation is None
    assert evidence.clean
    assert [item.value for item in evidence.operator_attested_absent_upstream] == ["640000.00"]
