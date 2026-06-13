"""AEAT filing-evidence conflict regressions for the overview calendar."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from ....adapters.outbound.aeat.sede import Declaracion
from ....domain.calculations.registry import CasillaObservation, RegistryModeloObservation
from ....domain.modelos import ExternalEvidence, ExternalEvidenceKind
from ...calculations._observations_repository import _ObservationEnvelopePayload
from ...live._expedientes import PersistedExpedientesSnapshot
from .. import (
    OverviewAeatSubmissionState,
    OverviewCalendarRange,
    build_overview_calendar,
    calendar_events_from_expedientes_snapshots,
    calendar_filing_evidence_from_sources,
)
from .test_calendar import (
    _FILED_JUSTIFICANTE_STORAGE_REF,
    _PERIOD_2025_1T,
    _SOURCE_URL,
    _filed_declaration_artefact,
    _filed_declaration_observation,
    _justificante_metadata,
    _modelo_record,
    _profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_calendar_entry_warns_when_local_and_filed_history_aeat_references_disagree() -> None:
    """A verified filed-history row must not hide a different local AEAT evidence reference."""
    local_ref = "LOCAL-LIVE-CAPTURE-CSV"
    remote_ref = "12345678901234567890"
    verified_csv = "CSVFILED3031T2025"
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="3" * 64,
                bucket_id="bucket-1",
                captured_at=datetime(2025, 4, 16, 10, 0, tzinfo=UTC),
                source_url=_SOURCE_URL,
                declarations=(
                    Declaracion(
                        modelo="303",
                        ejercicio=2025,
                        period=_PERIOD_2025_1T,
                        expediente_id=remote_ref,
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
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=ExternalEvidence(
                    kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    reference_id=local_ref,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
            ),
        ),
        observed_events=event,
        filed_declaration_observations=(
            _filed_declaration_observation(
                artefacts=(_filed_declaration_artefact(),),
                expediente_id=remote_ref,
            ),
        ),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: verified_csv},
        expected_tax_id="X1234567L",
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
        events=event,
        filing_evidence=evidence,
    )

    row = next(
        entry.filing_evidence
        for entry in calendar.entries
        if entry.modelo == "303" and entry.filing_year == 2025 and entry.period == _PERIOD_2025_1T
    )
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.justificante_verified is True
    assert row.verified_justificante_csv == verified_csv
    assert row.aeat_evidence_conflict_reference_ids == (remote_ref, local_ref)
    warning = next(item for item in calendar.warnings if item.code == "filing.aeat_evidence_conflict")
    assert warning.affected_modelos == ("303",)
    assert warning.fix_command == "aeat app live filed pull --modelo 303 --year 2025 --period 1T"


def test_calendar_does_not_conflict_live_capture_csv_with_matching_filed_history_csv() -> None:
    """A local live-capture CSV and filed-history expediente can point to the same receipt."""
    csv = "CSVFILED3031T2025"
    expediente_id = "12345678901234567890"
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
        filed_declaration_observations=(
            _filed_declaration_observation(
                artefacts=(_filed_declaration_artefact(),),
                expediente_id=expediente_id,
            ),
        ),
        verified_filed_declaration_artefact_refs=(_FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={_FILED_JUSTIFICANTE_STORAGE_REF: csv},
        expected_tax_id="X1234567L",
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
        filing_evidence=evidence,
    )

    row = next(
        entry.filing_evidence
        for entry in calendar.entries
        if entry.modelo == "303" and entry.filing_year == 2025 and entry.period == _PERIOD_2025_1T
    )
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.verified_justificante_csv == csv
    assert row.aeat_evidence_conflict_reference_ids == ()
    assert "filing.aeat_evidence_conflict" not in {warning.code for warning in calendar.warnings}


def test_calendar_does_not_conflict_matching_verified_csv_across_reference_namespaces() -> None:
    """CSV-backed local evidence and expediente-backed filed-history evidence can describe the same receipt."""
    csv = "JUST-303-2025-1T"
    expediente_id = "12345678901234567890"
    payload = _ObservationEnvelopePayload(
        observation=RegistryModeloObservation(
            modelo="303",
            filing_year=2025,
            period="1T",
            observations=(CasillaObservation(casilla_id="01", value=Decimal("123.45")),),
        ),
        captured_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": expediente_id,
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
                filed_by="aeat-import",
            ),
        ),
        calculation_observations=(payload,),
        justificantes=(_justificante_metadata(csv=csv),),
        expected_tax_id="X1234567L",
    )

    calendar = build_overview_calendar(
        _profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        today=date(2025, 4, 10),
        filing_evidence=evidence,
    )

    row = next(
        entry.filing_evidence
        for entry in calendar.entries
        if entry.modelo == "303" and entry.filing_year == 2025 and entry.period == _PERIOD_2025_1T
    )
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.verified_justificante_csv == csv
    assert row.aeat_evidence_conflict_reference_ids == ()
    assert "filing.aeat_evidence_conflict" not in {warning.code for warning in calendar.warnings}
