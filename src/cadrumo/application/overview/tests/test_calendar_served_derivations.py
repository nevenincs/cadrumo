"""Tests for the decided values a calendar row serves beside its fields."""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from ....core.external_constants import OutputLanguage
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.deadlines.festivos import DeadlineHolidayCoverage
from ....domain.deadlines.models import ObligationStatus
from ...workbench_generation_public_contracts import PublicHomeAgendaEntry
from ..calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarFilingEvidence,
    OverviewCalendarScope,
    OverviewFilingStatus,
    OverviewLocalFilingState,
    OverviewPeriodState,
    days_until_close,
    deadline_scopes,
    decide_filing_status,
)
from ..home import HomeAgendaEntry
from ..read_calendar_item_projection import OverviewCalendarEntrySnapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_AEAT = OverviewAeatSubmissionState
_LOCAL = OverviewLocalFilingState
_PERIOD = OverviewPeriodState
_STATUS = OverviewFilingStatus
_SCOPE = OverviewCalendarScope

_YEAR = filing_year_envelope().horizon
_CLOSE = date(_YEAR, 10, 20)
_BEFORE = _CLOSE - timedelta(days=5)
_AFTER = _CLOSE + timedelta(days=3)
_OPENS = _CLOSE - timedelta(days=19)

_REFUSAL = "it does not decide"


@pytest.mark.parametrize(
    ("aeat", "expected"),
    [
        (_AEAT.JUSTIFICANTE_VERIFIED, _STATUS.RECEIPT_VERIFIED),
        (_AEAT.ACCEPTED, _STATUS.ACCEPTED),
        (_AEAT.SUBMITTED_OBSERVED, _STATUS.SUBMITTED),
    ],
)
@pytest.mark.parametrize("local", [None, *_LOCAL])
@pytest.mark.parametrize("period_state", list(_PERIOD))
def test_every_observed_aeat_state_outranks_local_and_period_state(
    aeat: OverviewAeatSubmissionState,
    expected: OverviewFilingStatus,
    local: OverviewLocalFilingState | None,
    period_state: OverviewPeriodState,
) -> None:
    status = decide_filing_status(aeat_submission_state=aeat, local_filing_state=local, period_state=period_state)
    assert status is expected
    assert status is not _STATUS.RECORDED_LOCALLY


@pytest.mark.parametrize("aeat", [None, _AEAT.NOT_OBSERVED])
@pytest.mark.parametrize("period_state", list(_PERIOD))
def test_an_imported_baseline_says_imported_whatever_the_period(
    aeat: OverviewAeatSubmissionState | None, period_state: OverviewPeriodState
) -> None:
    status = decide_filing_status(
        aeat_submission_state=aeat, local_filing_state=_LOCAL.EXTERNAL_BASELINE_IMPORTED, period_state=period_state
    )
    assert status is _STATUS.IMPORTED


@pytest.mark.parametrize("aeat", [None, _AEAT.NOT_OBSERVED])
@pytest.mark.parametrize("period_state", list(_PERIOD))
def test_a_ready_local_record_says_recorded_locally_without_aeat_evidence(
    aeat: OverviewAeatSubmissionState | None, period_state: OverviewPeriodState
) -> None:
    status = decide_filing_status(
        aeat_submission_state=aeat, local_filing_state=_LOCAL.READY_TO_FILE, period_state=period_state
    )
    assert status is _STATUS.RECORDED_LOCALLY


@pytest.mark.parametrize("aeat", [None, _AEAT.NOT_OBSERVED])
@pytest.mark.parametrize("local", [None, _LOCAL.NOT_READY_TO_FILE])
@pytest.mark.parametrize(
    ("period_state", "expected"),
    [
        (_PERIOD.DUE, _STATUS.DUE),
        (_PERIOD.LATE, _STATUS.OVERDUE),
        (_PERIOD.UNKNOWN, _STATUS.UNKNOWN),
        (_PERIOD.FILED, _STATUS.EVIDENCE_WITHHELD),
    ],
)
def test_without_stronger_evidence_the_period_state_decides(
    aeat: OverviewAeatSubmissionState | None,
    local: OverviewLocalFilingState | None,
    period_state: OverviewPeriodState,
    expected: OverviewFilingStatus,
) -> None:
    status = decide_filing_status(aeat_submission_state=aeat, local_filing_state=local, period_state=period_state)
    assert status is expected


def _home_entry_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "modelo": "303",
        "filing_year": _YEAR,
        "period": Period.from_year_and_code(_YEAR, "3T"),
        "due_on": _CLOSE,
        "period_state": _PERIOD.FILED,
        "local_filing_state": _LOCAL.NOT_READY_TO_FILE,
        "aeat_submission_state": _AEAT.NOT_OBSERVED,
        "due_on_text": "20 oct",
        "period_words": "3T",
        "words_language": OutputLanguage.ES,
    }
    payload.update(overrides)
    return payload


def test_home_masks_a_filed_period_with_no_visible_evidence_as_withheld() -> None:
    entry = HomeAgendaEntry.model_validate(_home_entry_payload())
    assert entry.filing_status is _STATUS.EVIDENCE_WITHHELD
    assert entry.model_dump(mode="json")["filing_status"] == "evidence_withheld"


def test_home_entry_serves_the_status_its_evidence_decides() -> None:
    entry = HomeAgendaEntry.model_validate(
        _home_entry_payload(period_state=_PERIOD.DUE, aeat_submission_state=_AEAT.ACCEPTED)
    )
    assert entry.model_dump(mode="json")["filing_status"] == "accepted"


def test_home_entry_canonical_round_trip_skips_the_computed_status() -> None:
    entry = HomeAgendaEntry.model_validate(_home_entry_payload())
    assert HomeAgendaEntry.model_validate_json(entry.model_dump_json(exclude_computed_fields=True)) == entry


def _public_home_payload(filing_status: str) -> dict[str, object]:
    return {
        "modelo": "303",
        "filing_year": _YEAR,
        "period": {"filing_year": _YEAR, "code": "3T"},
        "due_on": _CLOSE.isoformat(),
        "period_state": "filed",
        "local_filing_state": "not_ready_to_file",
        "aeat_submission_state": "not_observed",
        "due_on_text": "20 oct",
        "period_words": "3T",
        "words_language": "es",
        "filing_status_words": None,
        "filing_status": filing_status,
    }


def test_public_home_entry_stores_the_status_its_fields_decide() -> None:
    entry = PublicHomeAgendaEntry.model_validate_json(json.dumps(_public_home_payload("evidence_withheld")))
    assert entry.filing_status is _STATUS.EVIDENCE_WITHHELD
    assert PublicHomeAgendaEntry.model_validate_json(entry.model_dump_json()) == entry


@pytest.mark.parametrize("foreign", ["receipt_verified", "recorded_locally", "due"])
def test_public_home_entry_refuses_a_status_its_fields_do_not_decide(foreign: str) -> None:
    with pytest.raises(ValidationError, match=_REFUSAL):
        PublicHomeAgendaEntry.model_validate_json(json.dumps(_public_home_payload(foreign)))


def test_days_until_close_is_positive_before_zero_on_and_negative_after_the_close() -> None:
    kwargs = {"adjusted_closes_on": _CLOSE, "holiday_coverage": DeadlineHolidayCoverage.NATIONAL_ONLY}
    assert days_until_close(evaluated_on=_BEFORE, **kwargs) == 5
    assert days_until_close(evaluated_on=_CLOSE, **kwargs) == 0
    assert days_until_close(evaluated_on=_AFTER, **kwargs) == -3


def test_days_until_close_is_unknown_when_the_calendar_is_unavailable() -> None:
    assert (
        days_until_close(
            adjusted_closes_on=_CLOSE,
            evaluated_on=_BEFORE,
            holiday_coverage=DeadlineHolidayCoverage.CALENDAR_UNAVAILABLE,
        )
        is None
    )


def _scopes(
    *, evaluated_on: date, status: ObligationStatus, user_state: OverviewPeriodState, withheld: bool = False
) -> tuple[OverviewCalendarScope, ...]:
    return deadline_scopes(
        adjusted_closes_on=_CLOSE,
        evaluated_on=evaluated_on,
        status=status,
        user_state=user_state,
        aeat_evidence_withheld=withheld,
    )


def test_an_open_due_row_is_ahead_and_upcoming_including_on_the_closing_day() -> None:
    open_due = (_SCOPE.AHEAD, _SCOPE.UPCOMING)
    assert _scopes(evaluated_on=_BEFORE, status=ObligationStatus.DUE_SOON, user_state=_PERIOD.DUE) == open_due
    assert _scopes(evaluated_on=_CLOSE, status=ObligationStatus.DUE_TODAY, user_state=_PERIOD.DUE) == open_due


def test_a_closed_late_row_is_past_and_overdue() -> None:
    assert _scopes(evaluated_on=_AFTER, status=ObligationStatus.OVERDUE, user_state=_PERIOD.LATE) == (
        _SCOPE.PAST,
        _SCOPE.OVERDUE,
    )


def test_filed_rows_are_filed_and_past_only_once_closed() -> None:
    assert _scopes(evaluated_on=_BEFORE, status=ObligationStatus.FILED, user_state=_PERIOD.FILED) == (
        _SCOPE.AHEAD,
        _SCOPE.FILED,
    )
    assert _scopes(evaluated_on=_AFTER, status=ObligationStatus.FILED, user_state=_PERIOD.FILED) == (
        _SCOPE.PAST,
        _SCOPE.FILED,
    )


def test_an_unknown_close_that_nominally_passed_is_neither_past_nor_ahead() -> None:
    assert _scopes(evaluated_on=_AFTER, status=ObligationStatus.UNKNOWN, user_state=_PERIOD.UNKNOWN) == ()


def test_an_unknown_close_whose_earliest_date_is_still_to_come_is_ahead() -> None:
    assert _scopes(evaluated_on=_BEFORE, status=ObligationStatus.UNKNOWN, user_state=_PERIOD.UNKNOWN) == (_SCOPE.AHEAD,)
    assert _scopes(evaluated_on=_CLOSE, status=ObligationStatus.UNKNOWN, user_state=_PERIOD.UNKNOWN) == (_SCOPE.AHEAD,)


def test_a_closed_not_applicable_row_is_past_but_neither_late_nor_upcoming() -> None:
    assert _scopes(evaluated_on=_AFTER, status=ObligationStatus.NOT_APPLICABLE, user_state=_PERIOD.UNKNOWN) == (
        _SCOPE.PAST,
    )


def test_evidence_unknown_only_when_aeat_evidence_is_withheld() -> None:
    assert _scopes(evaluated_on=_BEFORE, status=ObligationStatus.UPCOMING, user_state=_PERIOD.DUE) == (
        _SCOPE.AHEAD,
        _SCOPE.UPCOMING,
    )
    assert _scopes(evaluated_on=_BEFORE, status=ObligationStatus.UPCOMING, user_state=_PERIOD.DUE, withheld=True) == (
        _SCOPE.AHEAD,
        _SCOPE.UPCOMING,
        _SCOPE.EVIDENCE_UNKNOWN,
    )
    unknown = _scopes(evaluated_on=_AFTER, status=ObligationStatus.UNKNOWN, user_state=_PERIOD.UNKNOWN, withheld=True)
    assert unknown == (_SCOPE.EVIDENCE_UNKNOWN,)


def test_scopes_follow_enum_declaration_order() -> None:
    scopes = _scopes(evaluated_on=_AFTER, status=ObligationStatus.OVERDUE, user_state=_PERIOD.LATE, withheld=True)
    assert scopes == (_SCOPE.PAST, _SCOPE.OVERDUE, _SCOPE.EVIDENCE_UNKNOWN)
    assert [scope.value for scope in _SCOPE] == ["past", "ahead", "upcoming", "overdue", "filed", "evidence_unknown"]


def _entry(
    *,
    evaluated_on: date = _BEFORE,
    status: ObligationStatus = ObligationStatus.DUE_SOON,
    user_state: OverviewPeriodState = _PERIOD.DUE,
    days_overdue: int | None = None,
    evidence: OverviewCalendarFilingEvidence | None = None,
) -> OverviewCalendarEntry:
    return OverviewCalendarEntry(
        modelo="303",
        period=Period.from_year_and_code(_YEAR, "3T"),
        opens_on=_OPENS,
        closes_on=_CLOSE,
        adjusted_closes_on=_CLOSE,
        shift_reason="none",
        holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
        evaluated_on=evaluated_on,
        days_overdue=days_overdue,
        status=status,
        user_state=user_state,
        filing_year=_YEAR,
        filing_evidence=evidence if evidence is not None else OverviewCalendarFilingEvidence(),
    )


def test_a_row_serves_the_values_its_own_fields_decide() -> None:
    served = _entry().model_dump(mode="json")
    assert served["days_until_close"] == 5
    assert served["filing_status"] == "due"
    assert served["scopes"] == ["ahead", "upcoming"]


def test_a_row_with_a_ready_local_record_serves_recorded_locally() -> None:
    evidence = OverviewCalendarFilingEvidence(local_filing_state=_LOCAL.READY_TO_FILE)
    assert _entry(evidence=evidence).model_dump(mode="json")["filing_status"] == "recorded_locally"


def test_an_overdue_row_serves_negative_days_and_both_scopes() -> None:
    served = _entry(
        evaluated_on=_AFTER, status=ObligationStatus.OVERDUE, user_state=_PERIOD.LATE, days_overdue=3
    ).model_dump(mode="json")
    assert served["days_until_close"] == -3
    assert served["filing_status"] == "overdue"
    assert served["scopes"] == ["past", "overdue"]


def test_a_canonical_row_round_trips_without_its_computed_values() -> None:
    entry = _entry()
    assert OverviewCalendarEntry.model_validate_json(entry.model_dump_json(exclude_computed_fields=True)) == entry


def test_a_canonical_row_refuses_a_served_computed_key_it_does_not_declare() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        OverviewCalendarEntry.model_validate_json(_entry().model_dump_json())


def test_a_snapshot_stores_the_derivations_its_row_decides_and_round_trips() -> None:
    snapshot = OverviewCalendarEntrySnapshot.from_entry(_entry())
    assert snapshot.days_until_close == 5
    assert snapshot.filing_status is _STATUS.DUE
    assert snapshot.scopes == (_SCOPE.AHEAD, _SCOPE.UPCOMING)
    assert OverviewCalendarEntrySnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot


@pytest.mark.parametrize(
    ("name", "foreign"),
    [("filing_status", "accepted"), ("days_until_close", 6), ("scopes", ["past"])],
)
def test_a_snapshot_refuses_a_derivation_it_does_not_decide(name: str, foreign: object) -> None:
    payload = json.loads(OverviewCalendarEntrySnapshot.from_entry(_entry()).model_dump_json())
    payload[name] = foreign
    with pytest.raises(ValidationError, match=_REFUSAL):
        OverviewCalendarEntrySnapshot.model_validate_json(json.dumps(payload))


def test_home_words_its_date_and_period_in_the_served_language() -> None:
    entry = HomeAgendaEntry.worded(
        modelo="303",
        filing_year=_YEAR,
        period=Period.from_year_and_code(_YEAR, "3T"),
        due_on=_CLOSE,
        period_state=_PERIOD.DUE,
        local_filing_state=_LOCAL.NOT_READY_TO_FILE,
        aeat_submission_state=_AEAT.NOT_OBSERVED,
        language=OutputLanguage.EN,
    )
    assert entry.words_language is OutputLanguage.EN
    assert entry.due_on_text == f"Oct 20, {_YEAR}"
    assert entry.period_words == f"3rd quarter {_YEAR}"
