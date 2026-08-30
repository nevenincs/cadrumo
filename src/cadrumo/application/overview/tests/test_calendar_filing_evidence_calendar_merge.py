"""Calendar merge and warning coverage for overview filing evidence."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....core import Period
from ...live.expedientes import PersistedExpedientesSnapshot
from ..calendar import calendar_events_from_expedientes_snapshots
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import OverviewAeatSubmissionState, OverviewCalendarRange, OverviewLocalFilingState
from .calendar_test_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .calendar_test_support import (
    FILED_JUSTIFICANTE_STORAGE_REF as _FILED_JUSTIFICANTE_STORAGE_REF,
)
from .calendar_test_support import (
    PERIOD_2025_1T as _PERIOD_2025_1T,
)
from .calendar_test_support import (
    SOURCE_URL as _SOURCE_URL,
)
from .calendar_test_support import (
    calendar_with_evidence as _calendar_with_evidence,
)
from .calendar_test_support import (
    filed_declaration_artefact as _filed_declaration_artefact,
)
from .calendar_test_support import (
    filed_declaration_observation as _filed_declaration_observation,
)
from .calendar_test_support import (
    modelo_record as _modelo_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_calendar_entry_carries_distinct_local_and_aeat_states() -> None:
    record = _modelo_record()
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567890",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )
    evidence = calendar_filing_evidence_from_sources(filing_records=(record,), observed_events=event)

    calendar = _calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    matching = [entry for entry in calendar.entries if entry.modelo == "303" and entry.filing_year == 2025]
    assert matching, [(entry.modelo, entry.period, entry.filing_year) for entry in calendar.entries]
    row = matching[0].filing_evidence
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.justificante_verified is False


def test_calendar_warns_when_aeat_submission_lacks_verified_justificante() -> None:
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567890",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )
    evidence = calendar_filing_evidence_from_sources(observed_events=event)

    calendar = _calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    warning = next(item for item in calendar.warnings if item.code == "filing.justificante_unverified")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_action.action.action_id == "operator.live.filed.pull"
    assert {binding.argument_name: binding.value for binding in warning.fix_action.argument_bindings} == {
        "modelos": "303",
        "year": 2025,
        "period": "1T",
    }


def test_calendar_uses_generic_justificante_fix_when_multiple_periods_need_pull() -> None:
    """A single warning that spans multiple periods must not pretend one pull is enough."""
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 7, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567890",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=Period.from_year_and_code(2025, "2T"),
                        expediente_id="12345678901234567891",
                        estado="ALTA",
                        presented_at=datetime(2025, 7, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 7, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 7, 31)),
    )
    evidence = calendar_filing_evidence_from_sources(observed_events=event)

    calendar = _calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
        calendar_range=OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 7, 31)),
    )

    warning = next(item for item in calendar.warnings if item.code == "filing.justificante_unverified")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_action.action.action_id == "operator.live.filed.pull"
    assert warning.fix_action.argument_bindings == ()


def test_calendar_clears_justificante_warning_when_filed_history_verifies_receipt() -> None:
    csv = "CSVFILED3031T2025"
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567890",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )
    evidence = calendar_filing_evidence_from_sources(
        observed_events=event,
        filed_declaration_observations=(_filed_declaration_observation(artefacts=(_filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: csv},
    )

    calendar = _calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    assert "filing.justificante_unverified" not in {item.code for item in calendar.warnings}


def test_calendar_event_carries_verified_justificante_from_filed_observation() -> None:
    csv = "CSVFILED3031T2025"
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="1" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567890",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(_filed_declaration_observation(artefacts=(_filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: csv},
    )

    calendar = _calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    assert len(calendar.events) == 1
    assert calendar.events[0].aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert calendar.events[0].justificante_verified is True
    assert calendar.events[0].verified_justificante_csv == csv


def test_calendar_event_justificante_verification_is_expediente_specific() -> None:
    csv = "CSVFILED3031T2025"
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="2" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567890",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id="12345678901234567891",
                        estado="ALTA",
                        presented_at=datetime(2025, 4, 16, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(_filed_declaration_observation(artefacts=(_filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: csv},
    )

    calendar = _calendar_with_evidence(
        events=event,
        filing_evidence=evidence,
    )

    by_ref = {observed.reference_id: observed for observed in calendar.events}
    assert by_ref["12345678901234567890"].aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert by_ref["12345678901234567890"].justificante_verified is True
    assert by_ref["12345678901234567890"].verified_justificante_csv == csv
    assert by_ref["12345678901234567891"].aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert by_ref["12345678901234567891"].justificante_verified is False
