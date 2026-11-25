"""The Modelo 200 finding raised when the held preceding return and the stated twelve-month turnover disagree.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production observation store, profile projection and reader. For a
twelve-month preceding período both figures are that período's own turnover,
so a difference is a blocking finding carrying both, and neither is taken over
the other. Every year is taken from the published support envelope.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....application.modelo.incn_periodo_anterior import INCN_PERIODO_ANTERIOR_BINDING_ID
from ....application.modelo.incn_periodo_anterior_finding import (
    INCN_PERIODO_ANTERIOR_DISAGREES_KEY,
    incn_periodo_anterior_disagreement_finding,
)
from ....application.modelo.m303_regimen_simplificado_scope import active_taxpayer_profile
from ....core.authority_grade import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
)
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_preceding_m200_turnover

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "200"
_PERIOD = "0A"
_STATED = Decimal("7000000")
_HELD = Decimal("812345.67")


def _reading_years() -> tuple[int, ...]:
    with bundled_indexed_authority().operation() as operation:
        return tuple(
            year
            for year in operation.supported_filing_years().years
            if any(
                binding.id == INCN_PERIODO_ANTERIOR_BINDING_ID
                for binding in operation.snapshot(
                    _MODELO, filing_year=year, period=_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
                ).revision.bindings
            )
        )


_READING_YEARS = _reading_years()


def _entity(*, stated: Decimal, constitution: date) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="identity.tax_id", value="B00015016"),
        UserProfileFact(path="identity.legal_name", value="Test Company SL"),
        UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
        UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
        UserProfileFact(path="taxpayer_type.incn_prior_12_months", value=str(stated)),
        UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
        UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
        UserProfileFact(path="taxpayer_type.cierre_ejercicio_dia", value=31),
        UserProfileFact(path="taxpayer_type.cierre_ejercicio_mes", value=12),
        UserProfileFact(path="taxpayer_type.fecha_constitucion", value=constitution),
    )


@contextmanager
def _work(
    tmp_path: Path, year: int, *, stated: Decimal = _STATED, constitution: date | None = None
) -> Generator[SeededOperatorWork]:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path,
            modelo=_MODELO,
            filing_year=year,
            period_code=_PERIOD,
            extra_facts=_entity(stated=stated, constitution=constitution or date(year - 5, 1, 1)),
            estimation_regime=None,
        ) as work,
    ):
        yield work


def _hold_preceding_return(year: int) -> None:
    save_preceding_m200_turnover(
        CalculationObservationRepository(),
        filing_year=year,
        turnover=_HELD,
        captured_at=datetime(year, 1, 15, tzinfo=UTC),
    )


def _finding(work: SeededOperatorWork) -> ModeloVerificationFinding | None:
    ports = work.ports
    return incn_periodo_anterior_disagreement_finding(
        work_unit=work.work_unit,
        workflow_profile=active_taxpayer_profile(work.work_unit),
        operation=work.operation,
        observation_repository=ports.observation_repository,
        iva_compensation_history_repository=ports.iva_compensation_history_repository,
        calculation_repository=ports.calculation_repository,
        work_unit_repository=ports.work_unit_repository,
        filing_repository=ports.filing_repository,
    )


def test_some_supported_year_reads_the_preceding_turnover() -> None:
    assert _READING_YEARS


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_held_return_that_disagrees_with_the_stated_twelve_months_blocks_with_both(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year) as work:
        _hold_preceding_return(year)
        finding = _finding(work)

    assert finding is not None
    assert finding.kind is ModeloVerificationFindingKind.RECONCILIATION_MISMATCH
    assert finding.severity is ModeloVerificationFindingSeverity.BLOCKING
    assert finding.message_locale_key == INCN_PERIODO_ANTERIOR_DISAGREES_KEY
    assert finding.message_facts["held_turnover"] == _HELD
    assert finding.message_facts["stated_turnover"] == _STATED
    assert finding.message_facts["source_filing_year"] == year - 1
    assert finding.legal_refs


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_held_return_that_agrees_raises_nothing(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year, stated=_HELD) as work:
        _hold_preceding_return(year)
        assert _finding(work) is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_nothing_held_raises_nothing(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year) as work:
        assert _finding(work) is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_shorter_preceding_periodo_is_not_compared_with_the_twelve_months(tmp_path: Path, year: int) -> None:
    # Constituted in the middle of the preceding year: that período lasted less than twelve months,
    # so its own turnover is not the twelve-month one and the two are not expected to agree.
    with _work(tmp_path, year, constitution=date(year - 1, 7, 1)) as work:
        _hold_preceding_return(year)
        assert _finding(work) is None
