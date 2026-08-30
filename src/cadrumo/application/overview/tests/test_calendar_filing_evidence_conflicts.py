"""AEAT filing-evidence conflict regressions for the overview calendar."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ...live.expedientes import PersistedExpedientesSnapshot
from ..calendar import build_overview_calendar, calendar_events_from_expedientes_snapshots
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import OverviewAeatSubmissionState, OverviewCalendarRange
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
    calculation_observation_payload as _calculation_observation_payload,
)
from .calendar_test_support import (
    external_evidence as _external_evidence,
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


def test_calendar_entry_warns_when_local_and_filed_history_aeat_references_disagree() -> None:
    """A verified filed-history row must not hide a different local AEAT evidence reference."""
    local_ref = "LOCAL-LIVE-CAPTURE-CSV"
    remote_ref = "12345678901234567890"
    verified_csv = "CSVFILED3031T2025"
    event = calendar_events_from_expedientes_snapshots(
        (
            PersistedExpedientesSnapshot(
                snapshot_id="3" * 64,
                bucket_id=_BUCKET_ID,
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
                external_evidence=_external_evidence(
                    ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    local_ref,
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
    assert warning.fix_action.action.action_id == "operator.live.filed.pull"
    assert {binding.argument_name: binding.value for binding in warning.fix_action.argument_bindings} == {
        "modelos": "303",
        "year": 2025,
        "period": "1T",
    }


def test_calendar_does_not_conflict_live_capture_csv_with_matching_filed_history_csv() -> None:
    """A local live-capture CSV and filed-history expediente can point to the same receipt."""
    csv = "CSVFILED3031T2025"
    expediente_id = "12345678901234567890"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(
                    ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    csv,
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
    csv = "JUST3032025X1T7"
    expediente_id = "12345678901234567890"
    payload = _calculation_observation_payload(
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
                external_evidence=_external_evidence(
                    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    csv,
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
