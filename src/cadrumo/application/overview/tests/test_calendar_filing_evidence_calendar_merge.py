"""Calendar merge and warning coverage for overview filing evidence."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import OverviewAeatSubmissionState, OverviewCalendarRange, OverviewLocalFilingState
from .calendar_test_support import (
    FILED_JUSTIFICANTE_STORAGE_REF,
    PERIOD_2025_1T,
    calendar_with_evidence,
    expediente_declaration,
    expedientes_filing_events,
    filed_declaration_artefact,
    filed_declaration_observation,
    modelo_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# The shared expediente fixtures file the first quarter of this exercise.
_YEAR = PERIOD_2025_1T.filing_year


def test_calendar_entry_carries_distinct_local_and_aeat_states() -> None:
    record = modelo_record()
    event = expedientes_filing_events(expediente_declaration("12345678901234567890"))
    evidence = calendar_filing_evidence_from_sources(filing_records=(record,), observed_events=event)

    calendar = calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    matching = [entry for entry in calendar.entries if entry.modelo == "303" and entry.filing_year == _YEAR]
    assert matching, [(entry.modelo, entry.period, entry.filing_year) for entry in calendar.entries]
    row = matching[0].filing_evidence
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.justificante_verified is False


def test_calendar_warns_when_aeat_submission_lacks_verified_justificante() -> None:
    event = expedientes_filing_events(expediente_declaration("12345678901234567890"))
    evidence = calendar_filing_evidence_from_sources(observed_events=event)

    calendar = calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    warning = next(item for item in calendar.warnings if item.code == "filing.justificante_unverified")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_action.action.action_id == "operator.live.filed.pull"
    assert {binding.argument_name: binding.value for binding in warning.fix_action.argument_bindings} == {
        "modelos": "303",
        "year": _YEAR,
        "period": "1T",
    }


def test_calendar_uses_generic_justificante_fix_when_multiple_periods_need_pull() -> None:
    """A single warning that spans multiple periods must not pretend one pull is enough."""
    july_range = OverviewCalendarRange(from_date=date(_YEAR, 4, 1), to_date=date(_YEAR, 7, 31))
    event = expedientes_filing_events(
        expediente_declaration("12345678901234567890"),
        expediente_declaration(
            "12345678901234567891",
            presented_at=datetime(_YEAR, 7, 15, 9, 30, tzinfo=UTC),
            period=Period.from_year_and_code(_YEAR, "2T"),
        ),
        captured_at=datetime(_YEAR, 7, 16, 10, 0, tzinfo=UTC),
        calendar_range=july_range,
    )
    evidence = calendar_filing_evidence_from_sources(observed_events=event)

    calendar = calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
        calendar_range=july_range,
    )

    warning = next(item for item in calendar.warnings if item.code == "filing.justificante_unverified")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_action.action.action_id == "operator.live.filed.pull"
    assert warning.fix_action.argument_bindings == ()


def test_calendar_clears_justificante_warning_when_filed_history_verifies_receipt() -> None:
    csv = "CSVFILED3031T2025"
    event = expedientes_filing_events(expediente_declaration("12345678901234567890"))
    evidence = calendar_filing_evidence_from_sources(
        observed_events=event,
        filed_declaration_observations=(filed_declaration_observation(artefacts=(filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={FILED_JUSTIFICANTE_STORAGE_REF: csv},
    )

    calendar = calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    assert "filing.justificante_unverified" not in {item.code for item in calendar.warnings}


def test_calendar_event_carries_verified_justificante_from_filed_observation() -> None:
    csv = "CSVFILED3031T2025"
    event = expedientes_filing_events(expediente_declaration("12345678901234567890"), snapshot_id="1" * 64)
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(filed_declaration_observation(artefacts=(filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={FILED_JUSTIFICANTE_STORAGE_REF: csv},
    )

    calendar = calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    assert len(calendar.events) == 1
    assert calendar.events[0].aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert calendar.events[0].justificante_verified is True
    assert calendar.events[0].verified_justificante_csv == csv


def test_calendar_event_justificante_verification_is_expediente_specific() -> None:
    csv = "CSVFILED3031T2025"
    event = expedientes_filing_events(
        expediente_declaration("12345678901234567890"),
        expediente_declaration("12345678901234567891", presented_at=datetime(_YEAR, 4, 16, 9, 30, tzinfo=UTC)),
        snapshot_id="2" * 64,
    )
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(filed_declaration_observation(artefacts=(filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={FILED_JUSTIFICANTE_STORAGE_REF: csv},
    )

    calendar = calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    by_ref = {observed.reference_id: observed for observed in calendar.events}
    assert by_ref["12345678901234567890"].aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert by_ref["12345678901234567890"].justificante_verified is True
    assert by_ref["12345678901234567890"].verified_justificante_csv == csv
    assert by_ref["12345678901234567891"].aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert by_ref["12345678901234567891"].justificante_verified is False
