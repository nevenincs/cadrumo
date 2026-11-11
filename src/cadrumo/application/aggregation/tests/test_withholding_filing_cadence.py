"""The withholding cadence agrees with the filing schedule the calendar shows the operator.

Every filer here is a real profile record under the published authority's
schema, and every verdict comes from the published Modelo 111, 115 and 123
filing schedules through the resolver the deadline engine uses.
"""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.aggregation.tests.withholding_filer_profile_support import (
    LARGE_COMPANY_FACTS,
    PUBLIC_ADMINISTRATION_FACTS,
    REDEME_FACTS,
    withholding_filer_cadence,
    withholding_work_profile,
)
from cadrumo.application.aggregation.withholding_filing_cadence import (
    WithholdingFilingCadenceError,
    load_bucket_withholding_filer_cadence,
    quarterly_withholding_capture_period,
    require_quarterly_withholding_source,
    withholding_filer_cadence_for_work_profile,
)
from cadrumo.application.user_profile.projections import projection_for_taxpayer
from cadrumo.core.operator_action_enums import ActionConditionality, NoRecoveryOutcome
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.deadlines.engine import DeadlineEngine
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_QUARTERS = ("1T", "2T", "3T", "4T")
_MONTHS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")


def _calendar_periods(
    operation: PinnedAuthorityOperation,
    *,
    modelo: str,
    filing_year: int,
    facts: tuple[UserProfileFact, ...],
) -> set[str]:
    """Return the periods whose deadline window the engine's schedule gate admits for this filer."""
    profile = withholding_work_profile(operation, facts=facts)
    taxpayer = projection_for_taxpayer(profile.record, schema=profile.profile_decode_context.schema)
    engine = DeadlineEngine(authority=operation)
    return {
        window.period.registry_token
        for code, revision, window in engine.deadline_windows(filing_year)
        if code == modelo and engine.schedule_applies(taxpayer, revision, window)
    }


def test_an_ordinary_filer_is_quarterly_for_every_withholding_modelo(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR)

    for modelo in ("111", "115", "123"):
        schedule = cadence.schedule_for(modelo)
        assert schedule.quarterly_periods == _QUARTERS, modelo
        assert schedule.scheduled_periods == _QUARTERS, modelo
        assert schedule.unscheduled_quarters == (), modelo


def test_a_large_company_files_every_withholding_modelo_monthly(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """RIRPF art. 108.1 gives all three modelos the same monthly plazo for this retenedor."""
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=LARGE_COMPANY_FACTS)

    for modelo in ("111", "115", "123"):
        schedule = cadence.schedule_for(modelo)
        assert schedule.scheduled_periods == _MONTHS, modelo
        assert schedule.unscheduled_quarters == _QUARTERS, modelo


def test_a_public_administration_over_the_threshold_is_monthly_for_111_only(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=PUBLIC_ADMINISTRATION_FACTS)

    assert cadence.schedule_for("111").scheduled_periods == _MONTHS
    assert cadence.schedule_for("123").quarterly_periods == _QUARTERS


def test_redeme_enrolment_does_not_change_the_withholding_schedule(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=REDEME_FACTS)

    assert cadence.schedule_for("111").quarterly_periods == _QUARTERS
    assert cadence.schedule_for("123").quarterly_periods == _QUARTERS


@pytest.mark.parametrize(
    "facts",
    [(), LARGE_COMPANY_FACTS, PUBLIC_ADMINISTRATION_FACTS],
    ids=["ordinary", "large-company", "public-administration"],
)
def test_the_modelo_111_cadence_matches_the_calendar_windows(
    authority_operation: PinnedAuthorityOperation,
    facts: tuple[UserProfileFact, ...],
) -> None:
    """The periods the cadence assigns are exactly the 111 windows the deadline engine admits."""
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=facts)

    assert set(cadence.schedule_for("111").scheduled_periods) == _calendar_periods(
        authority_operation, modelo="111", filing_year=_YEAR, facts=facts
    )


@pytest.mark.parametrize("modelo", ["115", "123"])
def test_a_large_company_has_the_monthly_calendar_windows_of_the_other_two_modelos(
    modelo: str,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The cadence and the calendar agree for 115 and 123 as they already did for 111."""
    admitted = _calendar_periods(authority_operation, modelo=modelo, filing_year=_YEAR, facts=LARGE_COMPANY_FACTS)

    assert admitted == set(_MONTHS)
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=LARGE_COMPANY_FACTS)
    assert set(cadence.schedule_for(modelo).scheduled_periods) == admitted


def test_a_quarterly_filer_captures_into_the_recognition_quarter(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR)

    period = quarterly_withholding_capture_period(cadence, modelo="111", recognized_on=date(_YEAR, 5, 14))

    assert period == Period.from_year_and_code(_YEAR, "2T")


def test_a_monthly_filer_capture_is_refused_with_a_no_action_verdict(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=LARGE_COMPANY_FACTS)

    with pytest.raises(WithholdingFilingCadenceError) as raised:
        quarterly_withholding_capture_period(cadence, modelo="111", recognized_on=date(_YEAR, 5, 14))

    error = raised.value
    assert error.refusal_code == "withholding_quarterly_window_not_scheduled"
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "aggregation.withholding.quarterly_window.scheduled"
    assert verdict.action is None
    assert verdict.conditionality is ActionConditionality.NOT_APPLICABLE
    assert verdict.no_recovery_outcome is NoRecoveryOutcome.OPERATOR_DECISION
    assert dict(verdict.evidence[0].values) == {
        "modelo": "111",
        "filing_year": str(_YEAR),
        "period": "2T",
        "scheduled_periods": "|".join(_MONTHS),
        "monthly_windows_supported": False,
    }


def test_a_large_company_capital_capture_is_refused_because_its_123_is_monthly(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Quarterly capture is still refused, now because the monthly cadence is scheduled."""
    cadence = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=LARGE_COMPANY_FACTS)

    with pytest.raises(WithholdingFilingCadenceError) as raised:
        quarterly_withholding_capture_period(cadence, modelo="123", recognized_on=date(_YEAR, 12, 15))

    context = raised.value.context
    assert context is not None
    assert context["period"] == "4T"
    assert context["scheduled_periods"] == "|".join(_MONTHS)


def test_the_annual_source_refuses_when_its_periodic_modelo_is_not_quarterly_all_year(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    ordinary = withholding_filer_cadence(authority_operation, filing_year=_YEAR)
    require_quarterly_withholding_source(ordinary, annual_modelo="190", source_modelo="111")

    monthly = withholding_filer_cadence(authority_operation, filing_year=_YEAR, facts=LARGE_COMPANY_FACTS)
    with pytest.raises(WithholdingFilingCadenceError) as raised:
        require_quarterly_withholding_source(monthly, annual_modelo="190", source_modelo="111")

    assert raised.value.refusal_code == "withholding_annual_source_not_quarterly"
    assert raised.value.context == {
        "annual_modelo": "190",
        "modelo": "111",
        "filing_year": str(_YEAR),
        "unscheduled_quarters": "|".join(_QUARTERS),
        "scheduled_periods": "|".join(_MONTHS),
        "monthly_windows_supported": False,
    }


def test_an_absent_work_profile_is_refused_rather_than_read_as_quarterly(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    with pytest.raises(WithholdingFilingCadenceError) as raised:
        withholding_filer_cadence_for_work_profile(None, filing_year=_YEAR, operation=authority_operation)

    assert raised.value.refusal_code == "withholding_filer_profile_absent"
    verdict = raised.value.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "aggregation.withholding.filer_profile.present"


def test_a_bucket_whose_profile_no_session_serves_is_refused(authority_operation: PinnedAuthorityOperation) -> None:
    """A capture path that cannot read the filer's profile refuses instead of assuming quarterly."""
    with pytest.raises(WithholdingFilingCadenceError) as raised:
        load_bucket_withholding_filer_cadence(
            bucket_id="5e0f1a2b-3c4d-4e5f-8a6b-7c8d9e0f1a2b",
            filing_year=_YEAR,
            operation=authority_operation,
        )

    assert raised.value.refusal_code == "withholding_filer_profile_absent"
