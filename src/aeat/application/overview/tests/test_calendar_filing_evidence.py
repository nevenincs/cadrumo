"""Filing-evidence tests for the overview calendar aggregator."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.sede import Declaracion
from ....core import Period
from ....domain.calculations.registry import (
    ApplicabilityVerdict,
    CasillaId,
    RegistryModeloObservation,
    validated_casilla_id,
)
from ....domain.deadlines import ObligationStatus
from ....domain.modelos import ExternalEvidence, ExternalEvidenceKind, ModeloRecord
from ....tests.registry_observations import registry_grounded_observations
from ...calculations import CalculationObservationRepository
from ...live._expedientes import PersistedExpedientesSnapshot
from ...live._justificante import JustificanteCaptureSnapshot
from ...live._snapshot_base import SnapshotLifecycleState
from .. import (
    OverviewAeatSubmissionState,
    OverviewCalendarEntry,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
    OverviewLocalFilingState,
    OverviewPeriodState,
    SuppressedCalendarEntry,
    build_overview_calendar,
    calendar_events_from_expedientes_snapshots,
    calendar_events_from_justificante_capture_snapshots,
    calendar_events_from_modelo_records,
    calendar_filing_evidence_from_sources,
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
    filed_declaration_artefact as _filed_declaration_artefact,
)
from .calendar_test_support import (
    filed_declaration_observation as _filed_declaration_observation,
)
from .calendar_test_support import (
    justificante_metadata as _justificante_metadata,
)
from .calendar_test_support import (
    modelo_record as _modelo_record,
)
from .calendar_test_support import (
    profile as _profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"overview filing evidence fixture casilla key {value!r} is not a CasillaId") from exc


_OBSERVED_CASILLA: CasillaId = _casilla_id("01")


def _observed_casilla_observations(value: Decimal):
    return registry_grounded_observations(
        modelo="303",
        filing_year=2025,
        period="1T",
        casilla_values={_OBSERVED_CASILLA: value},
    )


def _calculation_observation_payload(
    *,
    source_kind: str,
    source_metadata: dict[str, str] | None = None,
    value: Decimal = Decimal("123.45"),
) -> object:
    observation = RegistryModeloObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=_observed_casilla_observations(value),
    )
    if source_metadata is None:
        return CalculationObservationRepository.payload_type(
            observation=observation,
            captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
            source_kind=source_kind,
        )
    return CalculationObservationRepository.payload_type(
        observation=observation,
        captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        source_kind=source_kind,
        source_metadata=source_metadata,
    )


def _justificante_capture_snapshot(
    *,
    csv: str = "CSVLIVE3031T2025",
    modelo: str = "303",
    filing_year: int = 2025,
    period: Period = _PERIOD_2025_1T,
    expediente_id: str = "EXPEDIENTE3031T2025",
    state: SnapshotLifecycleState = SnapshotLifecycleState.ACTIVE,
) -> JustificanteCaptureSnapshot:
    pdf_bytes = f"{csv}-pdf".encode()
    return JustificanteCaptureSnapshot(
        snapshot_id=f"snapshot-{csv}",
        bucket_id="bucket-calendar",
        modelo=modelo,
        filing_year=filing_year,
        period=period,
        expediente_id=expediente_id,
        csv=csv,
        pdf_sha256="a" * 64,
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
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=csv,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
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
        justificantes=(_justificante_metadata(csv=csv, tax_id="B76543210"),),
        expected_tax_id="X1234567L",
    )
    events = calendar_events_from_justificante_capture_snapshots(
        (snapshot,),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        justificantes=(_justificante_metadata(csv=csv, tax_id="B76543210"),),
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
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=csv,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
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


def test_justificante_taxpayer_match_is_case_insensitive() -> None:
    csv = "CSVLIVE3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=csv,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv, tax_id="X1234567L"),),
        expected_tax_id="x1234567l",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_modelo_record_justificante_csv_match_is_case_insensitive() -> None:
    csv = "CSVLIVE3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=csv.lower(),
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_modelo_record_csv_register_external_evidence_is_justificante_backed() -> None:
    csv = "CSVREG3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_CSV_REGISTER,
                    reference_id=csv,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
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
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=csv.lower(),
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
            ),
        ),
        justificantes=(
            _justificante_metadata(csv=csv),
            _justificante_metadata(csv=csv.lower(), tax_id="Y7654321Z"),
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
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id="CSVLIVE3031T2025",
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
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


def test_bare_aeat_accepted_flag_without_external_evidence_is_not_submission_evidence() -> None:
    base = _modelo_record()
    legacy_payload = base.model_dump(mode="python")
    legacy_payload["aeat_accepted"] = True
    legacy_torn_record = ModeloRecord.model_construct(**legacy_payload)
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(legacy_torn_record,),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert row.aeat_reference_id is None
    assert row.justificante_verified is False


def test_external_evidence_without_acceptance_does_not_upgrade_submission_state() -> None:
    csv = "CSVLIVE303TORN"
    base = _modelo_record()
    legacy_payload = base.model_dump(mode="python")
    legacy_payload["external_evidence"] = ExternalEvidence(
        kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
        reference_id=csv,
        imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
    )
    legacy_payload["aeat_accepted"] = False
    legacy_torn_record = ModeloRecord.model_construct(**legacy_payload)

    evidence = calendar_filing_evidence_from_sources(
        filing_records=(legacy_torn_record,),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.READY_TO_FILE
    assert row.aeat_submission_state is OverviewAeatSubmissionState.NOT_OBSERVED
    assert row.aeat_reference_id == csv
    assert row.justificante_verified is False


def test_expedientes_event_marks_observed_submission_but_not_justificante_verified() -> None:
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="e" * 64,
                bucket_id="bucket-1",
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
                bucket_id="bucket-1",
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                authenticated_identity="Y7654321Z",
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
                bucket_id="bucket-1",
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
        verified_justificante_csv="JUST-303-2025-1T",
        justificante_verified=True,
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
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
    csv = "JUST-303-2025-1T"
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
    csv = "JUST-303-2025-1T"
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
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    reference_id=csv,
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
        pytest.param({"aeat_justificante_csv": "JUST-303-2025-1T"}, id="single-csv"),
        pytest.param({"aeat_justificante_csvs": "OTHER,JUST-303-2025-1T"}, id="plural-csvs"),
        pytest.param({"aeat_justificante_csv": "just-303-2025-1t"}, id="case-insensitive-csv"),
    ),
)
def test_sede_calculation_observation_with_matching_justificante_metadata_is_verified(
    justificante_metadata: dict[str, str],
) -> None:
    csv = "JUST-303-2025-1T"
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
    csv = "JUST-303-2025-1T"
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
            _justificante_metadata(csv=csv.lower(), tax_id="Y7654321Z"),
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
            "aeat_justificante_csv": "JUST-303-2025-1T",
            "authenticated_identity": "X1234567L",
        },
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv="JUST-303-2025-1T", tax_id="Y7654321Z"),),
        expected_tax_id="X1234567L",
    )

    assert evidence[0].aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert evidence[0].verified_justificante_csv is None
    assert evidence[0].justificante_verified is False


@pytest.mark.parametrize(
    ("source_metadata", "expected_tax_id", "justificante_csv"),
    (
        pytest.param(None, "X1234567L", None, id="missing-metadata"),
        pytest.param(
            {
                "aeat_register_status": "BAJA",
                "aeat_expediente_id": "12345678901234567890",
            },
            None,
            None,
            id="non-alta",
        ),
        pytest.param(
            {
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_justificante_csv": "JUST-303-2025-1T",
            },
            "X1234567L",
            "JUST-303-2025-1T",
            id="missing-register-reference",
        ),
        pytest.param(
            {
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "12345678901234567890",
            },
            "X1234567L",
            None,
            id="missing-authenticated-identity",
        ),
        pytest.param(
            {
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": "12345678901234567890",
                "authenticated_identity": "Y7654321Z",
            },
            "X1234567L",
            None,
            id="wrong-authenticated-identity",
        ),
    ),
)
def test_sede_calculation_observation_requires_valid_register_metadata(
    source_metadata: dict[str, str] | None,
    expected_tax_id: str | None,
    justificante_csv: str | None,
) -> None:
    payload = _calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata=source_metadata,
    )

    evidence = calendar_filing_evidence_from_sources(
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv=justificante_csv),) if justificante_csv is not None else (),
        expected_tax_id=expected_tax_id,
    )

    assert evidence == ()


def test_filed_declaration_observation_with_stored_justificante_marks_verified() -> None:
    csv = "CSVFILED3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(_filed_declaration_observation(artefacts=(_filed_declaration_artefact(),)),),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: csv},
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_evidence_kind == "aeat_justificante_pdf"
    assert row.aeat_reference_id == "12345678901234567890"
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_filed_declaration_observation_identity_match_is_case_insensitive() -> None:
    csv = "CSVFILED3031T2025"
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(
            _filed_declaration_observation(artefacts=(_filed_declaration_artefact(),)).model_copy(
                update={"authenticated_identity": "x1234567l"},
            ),
        ),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: csv},
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    assert evidence[0].aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert evidence[0].justificante_verified is True
    assert evidence[0].verified_justificante_csv == csv


def test_filed_declaration_observation_with_dangling_justificante_manifest_is_observed_only() -> None:
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(_filed_declaration_observation(artefacts=(_filed_declaration_artefact(),)),),
        expected_tax_id="X1234567L",
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.aeat_evidence_kind == "filed_declaration_observation"
    assert row.justificante_verified is False


def test_non_alta_filed_declaration_observation_does_not_mark_verified() -> None:
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(
            _filed_declaration_observation(
                artefacts=(_filed_declaration_artefact(),),
            ).model_copy(update={"status": "BAJA"}),
        ),
        expected_tax_id="X1234567L",
    )

    assert evidence == ()


def test_filed_declaration_observation_for_wrong_taxpayer_is_ignored() -> None:
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(
            _filed_declaration_observation(
                artefacts=(_filed_declaration_artefact(),),
            ).model_copy(update={"authenticated_identity": "Y7654321Z"}),
        ),
        expected_tax_id="X1234567L",
    )

    assert evidence == ()


def test_filed_declaration_observation_without_stored_justificante_is_observed_only() -> None:
    evidence = calendar_filing_evidence_from_sources(
        filed_declaration_observations=(
            _filed_declaration_observation(
                artefacts=(
                    _filed_declaration_artefact(
                        kind="submitted_file",
                        storage_ref="secure-object:financial:" + "e" * 64,
                    ),
                    _filed_declaration_artefact(storage_ref=None),
                ),
            ),
        ),
    )

    assert len(evidence) == 1
    row = evidence[0]
    assert row.aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert row.aeat_evidence_kind == "filed_declaration_observation"
    assert row.justificante_verified is False


def test_imported_justificante_record_marks_aeat_verified_without_implying_local_calculation() -> None:
    imported_at = datetime(2025, 4, 16, 11, 0, tzinfo=UTC)
    csv = "JUST-303-2025-1T"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    reference_id=csv,
                    imported_at=imported_at,
                ),
                filed_by="aeat-import",
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.aeat_evidence_kind == "aeat_justificante_pdf"
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == csv


def test_imported_justificante_record_for_wrong_taxpayer_is_not_verified() -> None:
    csv = "JUST-303-2025-1T"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    reference_id=csv,
                    imported_at=datetime(2025, 4, 16, 11, 0, tzinfo=UTC),
                ),
                filed_by="aeat-import",
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv, tax_id="Y7654321Z"),),
        expected_tax_id="X1234567L",
    )

    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
    assert row.aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED
    assert row.aeat_evidence_kind == "aeat_justificante_pdf"
    assert row.justificante_verified is False


@pytest.mark.parametrize(
    ("modelo", "filing_year", "period"),
    [
        pytest.param("130", 2025, _PERIOD_2025_1T, id="wrong-modelo"),
        pytest.param("303", 2024, _PERIOD_2025_1T, id="wrong-ejercicio"),
        pytest.param("303", 2025, Period.from_year_and_code(2025, "2T"), id="wrong-period"),
    ],
)
def test_imported_justificante_record_for_wrong_obligation_is_not_verified(
    modelo: str,
    filing_year: int,
    period: Period,
) -> None:
    csv = "JUST-303-2025-1T"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    reference_id=csv,
                    imported_at=datetime(2025, 4, 16, 11, 0, tzinfo=UTC),
                ),
                filed_by="aeat-import",
            ),
        ),
        justificantes=(_justificante_metadata(csv=csv, modelo=modelo, filing_year=filing_year, period=period),),
        expected_tax_id="X1234567L",
    )

    row = evidence[0]
    assert row.local_filing_state is OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED
    assert row.aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED
    assert row.aeat_evidence_kind == "aeat_justificante_pdf"
    assert row.justificante_verified is False


def test_calendar_entry_carries_distinct_local_and_aeat_states() -> None:
    record = _modelo_record()
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id="bucket-1",
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

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
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
                bucket_id="bucket-1",
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

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
        events=event,
        filing_evidence=evidence,
    )

    warning = next(item for item in calendar.warnings if item.code == "filing.justificante_unverified")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_command == "aeat app live filed pull --modelo 303 --year 2025 --period 1T"


def test_calendar_uses_generic_justificante_fix_when_multiple_periods_need_pull() -> None:
    """A single warning that spans multiple periods must not pretend one pull is enough."""
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id="bucket-1",
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

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 7, 31)),
        today=date(2025, 4, 10),
        events=event,
        filing_evidence=evidence,
    )

    warning = next(item for item in calendar.warnings if item.code == "filing.justificante_unverified")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_command == "aeat app live filed pull --modelo MODELO --year YEAR --period PERIOD"


def test_calendar_clears_justificante_warning_when_filed_history_verifies_receipt() -> None:
    csv = "CSVFILED3031T2025"
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="f" * 64,
                bucket_id="bucket-1",
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

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
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
                bucket_id="bucket-1",
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

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
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
                bucket_id="bucket-1",
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

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
        events=event,
        filing_evidence=evidence,
    )

    by_ref = {observed.reference_id: observed for observed in calendar.events}
    assert by_ref["12345678901234567890"].aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert by_ref["12345678901234567890"].justificante_verified is True
    assert by_ref["12345678901234567890"].verified_justificante_csv == csv
    assert by_ref["12345678901234567891"].aeat_submission_state is OverviewAeatSubmissionState.SUBMITTED_OBSERVED
    assert by_ref["12345678901234567891"].justificante_verified is False


# ---------------------------------------------------------------------
