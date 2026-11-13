"""The preceding período impositivo's INCN, read through the one canonical reader.

Real behaviour throughout: an isolated encrypted profile, the bundled authority,
the production observation store, edit executor and reader. The figure comes
from the held preceding Modelo 200, else from the filer's statement, else stays
unresolved with the statement door; it is never zero by default. Every year is
taken from the published support envelope.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from ....application.calculations.cross_period_clean_state import declared_attestable_carry_requirements
from ....application.modelo.edit_models import (
    ModeloBindingEditIntentV1,
    ModeloEditBindingAddressV1,
    ModeloEditBindingIntentKind,
)
from ....application.modelo.incn_periodo_anterior import (
    INCN_PERIODO_ANTERIOR_BINDING_ID,
    IncnPeriodoAnterior,
    IncnPeriodoAnteriorGap,
    IncnPeriodoAnteriorOrigin,
    IncnPeriodoAnteriorStores,
    resolve_incn_periodo_anterior,
)
from ....application.modelo.preconditions import ATTEST_PRIOR_VALUE_ACTION_ID
from ....application.modelo.work_form_service import modelo_form_snapshot
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.values import UserProfileFact
from ...adapter_composition import profile_adapter_composition
from ..modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from .observation_seeding_support import save_preceding_m200_turnover

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODELO = "200"
_PERIOD = "0A"
_ENTITY = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="identity.legal_name", value="Test Company SL"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.legal_entity_form", value="sl"),
    UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="7000000"),
    UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
    UserProfileFact(path="taxpayer_type.tributacion_estado_porcentaje", value=Decimal("100")),
)
_STATED = "640000.00"
_HELD = Decimal("812345.67")


def _years(*, reading: bool) -> tuple[int, ...]:
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
            is reading
        )


_READING_YEARS = _years(reading=True)
_OTHER_YEARS = _years(reading=False)


@contextmanager
def _work(tmp_path: Path, year: int) -> Generator[SeededOperatorWork]:
    with (
        profile_adapter_composition(),
        seeded_operator_work(
            tmp_path,
            modelo=_MODELO,
            filing_year=year,
            period_code=_PERIOD,
            extra_facts=_ENTITY,
            estimation_regime=None,
        ) as work,
    ):
        yield work


def _read(
    work: SeededOperatorWork,
    *,
    activity_start: datetime | None = None,
    twelve_month_statement: Decimal | None = None,
) -> IncnPeriodoAnterior:
    return resolve_incn_periodo_anterior(
        work.work_unit.bucket_id,
        work.work_unit.filing_year,
        stores=IncnPeriodoAnteriorStores.from_calculation_ports(work.ports),
        activity_start_date=None if activity_start is None else activity_start.date(),
        twelve_month_statement=twelve_month_statement,
    )


def _hold_preceding_return(year: int) -> None:
    save_preceding_m200_turnover(
        CalculationObservationRepository(),
        filing_year=year,
        turnover=_HELD,
        captured_at=datetime(year, 1, 15, tzinfo=UTC),
    )


def _assert_preceding_return(result: IncnPeriodoAnterior, year: int) -> None:
    assert result.binding_id == INCN_PERIODO_ANTERIOR_BINDING_ID
    assert (result.source_modelo, result.source_filing_year, result.source_period) == (_MODELO, year - 1, _PERIOD)


def test_some_supported_year_reads_the_preceding_turnover() -> None:
    assert _READING_YEARS


@pytest.mark.parametrize("year", _READING_YEARS)
def test_nothing_held_and_nothing_stated_stays_unresolved_with_the_statement_door(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year) as work:
        result = _read(work)

    _assert_preceding_return(result, year)
    assert result.origin is IncnPeriodoAnteriorOrigin.UNRESOLVED
    assert result.value is None
    assert not result.resolved
    assert result.gap is IncnPeriodoAnteriorGap.NO_RETURN_HELD
    assert result.door_action_id == ATTEST_PRIOR_VALUE_ACTION_ID


@pytest.mark.parametrize("year", _READING_YEARS)
def test_the_held_preceding_return_supplies_the_figure(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year) as work:
        _hold_preceding_return(year)
        result = _read(work)

    _assert_preceding_return(result, year)
    assert result.origin is IncnPeriodoAnteriorOrigin.HELD_RETURN
    assert result.value == _HELD
    assert result.gap is None
    assert result.door_action_id is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_the_filers_statement_supplies_the_figure_when_no_return_is_held(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year) as work:
        # The statement recalculates the declaration, so every other carry no held
        # return supplies is stated too, as zero.
        snapshot = modelo_form_snapshot(work.operation, work.work_unit.modelo, year, work.work_unit.period)
        statements = tuple(
            ModeloBindingEditIntentV1(
                address=ModeloEditBindingAddressV1(binding_id=binding_id),
                kind=ModeloEditBindingIntentKind.ATTEST_PRIOR_VALUE,
                value=Decimal(_STATED if binding_id == INCN_PERIODO_ANTERIOR_BINDING_ID else "0"),
            )
            for binding_id in declared_attestable_carry_requirements(snapshot)
        )
        applied = work.apply(binding=statements)
        assert applied.refusal is None, applied.refusal
        result = _read(work)

    _assert_preceding_return(result, year)
    assert result.origin is IncnPeriodoAnteriorOrigin.OPERATOR_STATEMENT
    assert result.value == Decimal(_STATED)
    assert result.door_action_id is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_preceding_period_before_the_activity_is_not_zero(tmp_path: Path, year: int) -> None:
    start = Period.from_year_and_code(year, _PERIOD).start_date
    with _work(tmp_path, year) as work:
        result = _read(work, activity_start=datetime(start.year, start.month, start.day, tzinfo=UTC))

    assert result.origin is IncnPeriodoAnteriorOrigin.UNRESOLVED
    assert result.value is None
    assert result.gap is IncnPeriodoAnteriorGap.PERIOD_BEFORE_ACTIVITY
    assert result.door_action_id == ATTEST_PRIOR_VALUE_ACTION_ID


@pytest.mark.parametrize("year", _OTHER_YEARS)
def test_an_edition_that_reads_no_preceding_turnover_says_so(tmp_path: Path, year: int) -> None:
    with _work(tmp_path, year) as work:
        result = _read(work)

    assert result.origin is IncnPeriodoAnteriorOrigin.UNRESOLVED
    assert result.gap is IncnPeriodoAnteriorGap.NOT_READ_BY_EDITION
    assert result.source_modelo is None
    assert result.door_action_id is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_twelve_month_preceding_periodo_takes_the_stated_twelve_month_turnover_when_nothing_is_held(
    tmp_path: Path, year: int
) -> None:
    with _work(tmp_path, year) as work:
        result = _read(work, twelve_month_statement=Decimal(_STATED))

    _assert_preceding_return(result, year)
    assert result.origin is IncnPeriodoAnteriorOrigin.TWELVE_MONTH_STATEMENT
    assert result.value == Decimal(_STATED)
    assert result.gap is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_held_return_agreeing_with_the_stated_twelve_month_turnover_supplies_the_figure(
    tmp_path: Path, year: int
) -> None:
    with _work(tmp_path, year) as work:
        _hold_preceding_return(year)
        result = _read(work, twelve_month_statement=_HELD)

    assert result.origin is IncnPeriodoAnteriorOrigin.HELD_RETURN
    assert result.value == _HELD


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_held_return_and_a_different_stated_twelve_month_turnover_leave_the_figure_unresolved_with_both(
    tmp_path: Path, year: int
) -> None:
    with _work(tmp_path, year) as work:
        _hold_preceding_return(year)
        result = _read(work, twelve_month_statement=Decimal(_STATED))

    _assert_preceding_return(result, year)
    assert result.origin is IncnPeriodoAnteriorOrigin.UNRESOLVED
    assert result.value is None
    assert result.gap is IncnPeriodoAnteriorGap.TWELVE_MONTH_STATEMENT_DISAGREES
    assert result.held_value == _HELD
    assert result.twelve_month_statement == Decimal(_STATED)
    assert result.door_action_id is None


@pytest.mark.parametrize("year", _READING_YEARS)
def test_a_preceding_period_before_the_activity_stays_unresolved_whatever_twelve_month_turnover_is_stated(
    tmp_path: Path, year: int
) -> None:
    start = Period.from_year_and_code(year, _PERIOD).start_date
    with _work(tmp_path, year) as work:
        result = _read(
            work,
            activity_start=datetime(start.year, start.month, start.day, tzinfo=UTC),
            twelve_month_statement=Decimal(_STATED),
        )

    # Before the activity the figure is the annualised first-period turnover (art. 101.2), never the profile's.
    assert result.origin is IncnPeriodoAnteriorOrigin.UNRESOLVED
    assert result.gap is IncnPeriodoAnteriorGap.PERIOD_BEFORE_ACTIVITY
