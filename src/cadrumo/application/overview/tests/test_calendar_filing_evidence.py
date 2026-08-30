"""Filing-evidence tests for the overview calendar aggregator."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....core.period import Period
from ....core.hashing import sha256_hex
from ....domain.calculations.registry.applicability import ApplicabilityVerdict
from ....domain.deadlines.models import ObligationStatus
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ...live.expedientes import PersistedExpedientesSnapshot
from ...live.justificante import JustificanteCaptureSnapshot, derive_justificante_capture_snapshot_id
from ...live.snapshot_base import SnapshotLifecycleState
from ..calendar import (
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_justificante_capture_snapshots,
    calendar_events_from_modelo_records,
)
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
    SuppressedCalendarEntry,
)
from .calendar_test_support import (
    BUCKET_ID as _BUCKET_ID,
)
from .calendar_test_support import (
    PERIOD_2025_1T as _PERIOD_2025_1T,
)
from .calendar_test_support import (
    SOURCE_URL as _SOURCE_URL,
)
from .calendar_test_support import (
    calculation_observation_payload as _calculation_observation_payload,
)
from .calendar_test_support import (
    calendar_with_evidence as _calendar_with_evidence,
)
from .calendar_test_support import (
    external_evidence as _external_evidence,
)
from .calendar_test_support import (
    justificante_metadata as _justificante_metadata,
)
from .calendar_test_support import (
    modelo_record as _modelo_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _justificante_capture_snapshot(
    *,
    csv: str = "CSVLIVE3031T2025",
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = _PERIOD_2025_1T,
    expediente_id: str = "20253031T2025",
    state: SnapshotLifecycleState = SnapshotLifecycleState.ACTIVE,
) -> JustificanteCaptureSnapshot:
    pdf_bytes = f"{csv}-pdf".encode()
    pdf_sha256 = sha256_hex(pdf_bytes)
    return JustificanteCaptureSnapshot(
        snapshot_id=derive_justificante_capture_snapshot_id(
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            pdf_sha256=pdf_sha256,
        ),
        bucket_id=_BUCKET_ID,
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        expediente_id=expediente_id,
        csv=csv,
        pdf_sha256=pdf_sha256,
        pdf_base64=base64.b64encode(pdf_bytes).decode("ascii"),
        captured_at=datetime(filing_year, 4, 16, 12, 0, tzinfo=UTC),
        state=state,
    )


def test_local_modelo_record_does_not_mark_aeat_submission() -> None:
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(_modelo_record(),),
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert row.justificante_required is True
    assert row.justificante_verified is False


def test_modelo_record_projects_local_filing_calendar_event() -> None:
    events = calendar_events_from_modelo_records(
        (_modelo_record(),),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type is OverviewCalendarEventType.FILING
    assert event.event_date == date(2025, 4, 14)
    assert event.source == "modelo_filing_record"
    assert event.reference_id
    assert event.modelo == "303"
    assert event.period == _PERIOD_2025_1T
    assert event.status == "ready_to_file:vigente"
    assert event.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert event.aeat_submitted_at is None
    assert event.justificante_verified is False


def test_modelo_record_calendar_event_reports_verified_aeat_justificante_axis() -> None:
    csv = "CSVLIVE3031T2025"
    events = calendar_events_from_modelo_records(
        (
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, csv),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_date == date(2025, 4, 15)
    assert event.status == "ready_to_file:vigente"
    assert event.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert event.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert event.justificante_verified is True
    assert event.verified_justificante_csv == csv


def test_justificante_capture_snapshot_projects_verified_calendar_event_without_local_record() -> None:
    csv = "CSVLIVE3031T2025"
    snapshot = _justificante_capture_snapshot(csv=csv)

    events = calendar_events_from_justificante_capture_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(events) == 1
    event = events[0]
    assert event.event_type is OverviewCalendarEventType.FILING
    assert event.event_date == date(2025, 4, 15)
    assert event.source == "aeat_sede_live_capture"
    assert event.reference_id == snapshot.expediente_id
    assert event.snapshot_id == snapshot.snapshot_id
    assert event.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert event.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert event.justificante_verified is True
    assert event.verified_justificante_csv == csv


def test_justificante_capture_snapshot_creates_verified_evidence_without_local_record() -> None:
    csv = "CSVLIVE3031T2025"
    snapshot = _justificante_capture_snapshot(csv=csv)

    evidence = calendar_filing_evidence_from_sources(
        justificante_capture_snapshots=(snapshot,),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.NOT_READY_TO_FILE
    assert row.local_filing_record_id is None
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_reference_id == snapshot.expediente_id
    assert row.aeat_snapshot_id == snapshot.snapshot_id
    assert row.aeat_evidence_kind == "aeat_sede_live_capture"
    assert row.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_justificante_capture_snapshot_requires_matching_taxpayer_metadata() -> None:
    csv = "CSVLIVE3031T2025"
    snapshot = _justificante_capture_snapshot(csv=csv)

    evidence = calendar_filing_evidence_from_sources(
        justificante_capture_snapshots=(snapshot,),
        justificantes=(_justificante_metadata(csv=csv, tax_id="B76543214"),),
        expected_tax_id="X1234567L",
    )
    events = calendar_events_from_justificante_capture_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        justificantes=(_justificante_metadata(csv=csv, tax_id="B76543214"),),
        expected_tax_id="X1234567L",
    )

    assert evidence == ()
    assert events == ()


def test_calendar_filing_evidence_refuses_contradictory_justificante_state() -> None:
    with pytest.raises(ValidationError):
        OverviewCalendarFilingEvidence(
            modelo="303",
            filing_year=2025,
            period=_PERIOD_2025_1T,
            aeat_submission_state=OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
            justificante_verified=False,
        )

    with pytest.raises(ValidationError):
        OverviewCalendarFilingEvidence(
            modelo="303",
            filing_year=2025,
            period=_PERIOD_2025_1T,
            aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
            justificante_verified=True,
        )


def test_calendar_event_refuses_contradictory_justificante_state() -> None:
    base = {
        "event_type": OverviewCalendarEventType.FILING,
        "event_date": date(2025, 4, 15),
        "source": "filed_declaration_observation",
        "summary": "Modelo 303 filed declaration",
        "reference_id": "12345678901234567890",
        "modelo": "303",
        "filing_year": 2025,
        "period": _PERIOD_2025_1T,
    }

    with pytest.raises(ValidationError):
        OverviewCalendarEvent.model_validate(
            {
                **base,
                "aeat_submission_state": OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
                "justificante_verified": False,
            },
        )

    with pytest.raises(ValidationError):
        OverviewCalendarEvent.model_validate(
            {
                **base,
                "aeat_submission_state": OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
                "justificante_verified": True,
            },
        )


def test_period_bearing_calendar_models_roundtrip_through_json() -> None:
    evidence = OverviewCalendarFilingEvidence(
        modelo="303",
        filing_year=2025,
        period=_PERIOD_2025_1T,
        local_filing_state=OverviewLocalFilingState.READY_TO_FILE,
    )
    event = OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.FILING,
        event_date=date(2025, 4, 15),
        source="filed_declaration_observation",
        summary="Modelo 303 filed declaration",
        reference_id="12345678901234567890",
        modelo="303",
        filing_year=2025,
        period=_PERIOD_2025_1T,
        aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
        justificante_verified=False,
    )
    entry = OverviewCalendarEntry(
        modelo="303",
        period=_PERIOD_2025_1T,
        opens_on=date(2025, 4, 1),
        closes_on=date(2025, 4, 20),
        adjusted_closes_on=date(2025, 4, 21),
        shift_reason="weekend",
        status=ObligationStatus.UPCOMING,
        user_state=OverviewPeriodState.DUE,
        filing_year=2025,
        filing_evidence=evidence,
    )
    suppressed = SuppressedCalendarEntry(
        modelo="390",
        period=Period.from_year_and_code(2025, "0A"),
        verdict=ApplicabilityVerdict.NOT_APPLICABLE,
        reason="not enrolled",
    )

    assert OverviewCalendarFilingEvidence.model_validate_json(evidence.model_dump_json()) == evidence
    assert OverviewCalendarEvent.model_validate_json(event.model_dump_json()) == event
    assert type(entry).model_validate_json(entry.model_dump_json()) == entry
    assert SuppressedCalendarEntry.model_validate_json(suppressed.model_dump_json()) == suppressed


def test_live_capture_external_evidence_requires_persisted_justificante_to_verify() -> None:
    csv = "CSVLIVE3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, csv),
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert row.aeat_evidence_kind == "aeat_live_capture"
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_modelo_record_justificante_matching_is_case_insensitive() -> None:
    csv = "CSVLIVE3031T2025"
    cases = (
        ("taxpayer-id", csv, csv, "X1234567L", "x1234567l"),
        ("csv", csv.lower(), csv, "X1234567L", "X1234567L"),
    )

    for case_id, evidence_csv, justificante_csv, justificante_tax_id, expected_tax_id in cases:
        evidence = calendar_filing_evidence_from_sources(
            filing_records=(
                _modelo_record(
                    aeat_accepted=True,
                    external_evidence=_external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, evidence_csv),
                ),
            ),
            justificantes=(_justificante_metadata(csv=justificante_csv, tax_id=justificante_tax_id),),
            expected_tax_id=expected_tax_id,
        )

        assert len(evidence) == 1, case_id
        row = evidence[0]
        assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED, case_id
        assert row.justificante_verified is True, case_id
        assert row.verified_justificante_csv == justificante_csv, case_id


def test_modelo_record_csv_register_external_evidence_is_justificante_backed() -> None:
    csv = "CSVREG3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(ExternalEvidenceKind.AEAT_CSV_REGISTER, csv),
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_evidence_kind == "aeat_csv_register"
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_modelo_record_case_equivalent_conflicting_justificantes_do_not_verify() -> None:
    csv = "CSVLIVE3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, csv.lower()),
            ),
        ),
        justificantes=(
            _justificante_metadata(csv=csv),
            _justificante_metadata(csv=csv.lower(), tax_id="Y7654321G"),
        ),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED
    assert row.justificante_verified is False
    assert row.verified_justificante_csv is None


def test_live_capture_external_evidence_without_metadata_is_not_justificante_verified() -> None:
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(ExternalEvidenceKind.AEAT_LIVE_CAPTURE, "CSVLIVE3031T2025"),
            ),
        ),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED
    assert row.aeat_submitted_at is None
    assert row.aeat_evidence_kind == "aeat_live_capture"
    assert row.justificante_verified is False


def test_expedientes_event_marks_observed_submission_but_not_justificante_verified() -> None:
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="e" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                authenticated_identity="X1234567L",
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
        filing_records=(_modelo_record(),),
        observed_events=event,
        expected_tax_id="X1234567L",
    )

    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert row.aeat_reference_id == "12345678901234567890"
    assert row.justificante_verified is False


def test_expedientes_event_for_wrong_authenticated_identity_is_not_submission_evidence() -> None:
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="e" * 64,
                bucket_id=_BUCKET_ID,
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                authenticated_identity="Y7654321G",
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
        expected_tax_id="X1234567L",
    )

    assert evidence == ()


def test_non_alta_expedientes_event_does_not_create_submission_evidence() -> None:
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
                        estado="BAJA",
                        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
                    ),
                ),
                persisted_at=datetime(2025, 4, 16, 10, 5, tzinfo=UTC),
            ),
        ),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
    )

    assert len(event) == 1
    assert event[0].status == "BAJA"
    assert event[0].aeat_submission_state is None

    evidence = calendar_filing_evidence_from_sources(observed_events=event)

    assert evidence == ()


def test_non_alta_calendar_event_is_not_enriched_by_matching_verified_evidence() -> None:
    event = OverviewCalendarEvent(
        event_type=OverviewCalendarEventType.FILING,
        event_date=date(2025, 4, 15),
        source="aeat_sede_expedientes",
        summary="Modelo 303 2025 1T filed at AEAT",
        reference_id="12345678901234567890",
        modelo="303",
        filing_year=2025,
        period=_PERIOD_2025_1T,
        status="BAJA",
    )
    verified_evidence = OverviewCalendarFilingEvidence(
        modelo="303",
        filing_year=2025,
        period=_PERIOD_2025_1T,
        aeat_submission_state=OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED,
        aeat_reference_id="12345678901234567890",
        verified_justificante_csv="JUST3032025X1T7",
        justificante_verified=True,
    )

    calendar = _calendar_with_evidence(
        events=(event,),
        filing_evidence=(verified_evidence,),
    )

    assert len(calendar.events) == 1
    assert calendar.events[0].status == "BAJA"
    assert calendar.events[0].aeat_submission_state is None
    assert calendar.events[0].justificante_verified is None


def test_sede_calculation_observation_is_not_justificante_verification() -> None:
    payload = _calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.aeat_reference_id == "12345678901234567890"
    assert row.aeat_evidence_kind == "aeat_sede_justificante"
    assert row.justificante_verified is False


@pytest.mark.parametrize("source_kind", ("aeat_sede_live_capture", "aeat_csv_register"))
def test_official_calculation_observation_sources_are_calendar_submission_evidence(source_kind: str) -> None:
    payload = _calculation_observation_payload(
        source_kind=source_kind,
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.period == _PERIOD_2025_1T
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.aeat_reference_id == "12345678901234567890"
    assert row.aeat_evidence_kind == source_kind
    assert row.justificante_verified is False


def test_official_calculation_observation_source_with_matching_justificante_is_verified() -> None:
    csv = "JUST3032025X1T7"
    payload = _calculation_observation_payload(
        source_kind="aeat_csv_register",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "aeat_justificante_csv": csv,
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_evidence_kind == "aeat_csv_register"
    assert row.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert row.verified_justificante_csv == csv
    assert row.justificante_verified is True


def test_verified_modelo_record_receipt_time_survives_calculation_observation_merge() -> None:
    csv = "JUST3032025X1T7"
    payload = _calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "aeat_justificante_csv": csv,
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(
                    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    csv,
                    imported_at=datetime(2025, 4, 16, 11, 0, tzinfo=UTC),
                ),
            ),
        ),
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_submitted_at == datetime(2025, 4, 15, 9, 30, tzinfo=UTC)
    assert row.verified_justificante_csv == csv
    assert row.justificante_verified is True


@pytest.mark.parametrize(
    "justificante_metadata",
    (
        pytest.param({"aeat_justificante_csv": "JUST3032025X1T7"}, id="single-csv"),
        pytest.param({"aeat_justificante_csvs": "OTHER,JUST3032025X1T7"}, id="plural-csvs"),
        pytest.param({"aeat_justificante_csv": "just3032025x1t7"}, id="case-insensitive-csv"),
    ),
)
def test_sede_calculation_observation_with_matching_justificante_metadata_is_verified(
    justificante_metadata: dict[str, str],
) -> None:
    csv = "JUST3032025X1T7"
    payload = _calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "authenticated_identity": "X1234567L",
            **justificante_metadata,
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_reference_id == "12345678901234567890"
    assert row.aeat_evidence_kind == "aeat_sede_justificante"
    assert row.verified_justificante_csv == csv
    assert row.justificante_verified is True


def test_sede_calculation_observation_conflicting_case_equivalent_justificantes_do_not_verify() -> None:
    csv = "JUST3032025X1T7"
    payload = _calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "aeat_justificante_csv": csv.lower(),
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        justificantes=(
            _justificante_metadata(csv=csv),
            _justificante_metadata(csv=csv.lower(), tax_id="Y7654321G"),
        ),
        expected_tax_id="X1234567L",
    )

    assert evidence[0].aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert evidence[0].justificante_verified is False
    assert evidence[0].verified_justificante_csv is None


def test_sede_calculation_observation_with_wrong_justificante_metadata_is_not_verified() -> None:
    payload = _calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": "12345678901234567890",
            "aeat_justificante_csv": "JUST3032025X1T7",
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv="JUST3032025X1T7", tax_id="Y7654321G"),),
        expected_tax_id="X1234567L",
    )

    assert evidence[0].aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert evidence[0].verified_justificante_csv is None
    assert evidence[0].justificante_verified is False


def test_sede_calculation_observation_requires_valid_register_metadata() -> None:
    cases = (
        ("missing-metadata", None, "X1234567L", None),
        (
            "non-alta",
            {
                "aeat_register_status": "BAJA",
                "aeat_expediente_id": "12345678901234567890",
            },
            None,
            None,
        ),
        (
            "missing-register-reference",
            {
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_justificante_csv": "JUST3032025X1T7",
            },
            "X1234567L",
            "JUST3032025X1T7",
        ),
        (
            "missing-authenticated-identity",
            {
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "12345678901234567890",
            },
            "X1234567L",
            None,
        ),
        (
            "wrong-authenticated-identity",
            {
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "12345678901234567890",
                "authenticated_identity": "Y7654321G",
            },
            "X1234567L",
            None,
        ),
    )

    for case_id, source_metadata, expected_tax_id, justificante_csv in cases:
        payload = _calculation_observation_payload(
            source_kind="aeat_sede_justificante",
            source_metadata=source_metadata,
        )

        evidence = calendar_filing_evidence_from_sources(
            calculation_observations=(payload,),
            justificantes=(_justificante_metadata(csv=justificante_csv),) if justificante_csv is not None else (),
            expected_tax_id=expected_tax_id,
        )

        assert evidence == (), case_id


# ---------------------------------------------------------------------
