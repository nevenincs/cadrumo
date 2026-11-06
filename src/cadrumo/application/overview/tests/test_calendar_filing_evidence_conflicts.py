"""AEAT filing-evidence conflict regressions for the overview calendar."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ..calendar import build_overview_calendar
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendar,
    OverviewCalendarFilingEvidence,
    OverviewCalendarRange,
)
from .calendar_test_support import (
    FILED_JUSTIFICANTE_STORAGE_REF,
    PERIOD_2025_1T,
    calculation_observation_payload,
    expediente_declaration,
    expedientes_filing_events,
    external_evidence,
    filed_declaration_artefact,
    filed_declaration_observation,
    justificante_metadata,
    modelo_record,
    profile,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _april_2025_303_filing_row(
    evidence: tuple[OverviewCalendarFilingEvidence, ...], operation: PinnedAuthorityOperation
) -> tuple[OverviewCalendar, OverviewCalendarFilingEvidence]:
    """Build the April 2025 calendar over ``evidence`` and return it with the 303 first-quarter evidence row."""
    calendar = build_overview_calendar(
        profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        operation=operation,
        today=date(2025, 4, 10),
        filing_evidence=evidence,
    )
    row = next(
        entry.filing_evidence
        for entry in calendar.entries
        if entry.modelo == "303" and entry.filing_year == 2025 and entry.period == PERIOD_2025_1T
    )
    return calendar, row


def test_calendar_entry_warns_when_local_and_filed_history_aeat_references_disagree(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A verified filed-history row must not hide a different local AEAT evidence reference."""
    local_ref = "LOCAL-LIVE-CAPTURE-CSV"
    remote_ref = "12345678901234567890"
    verified_csv = "CSVFILED3031T2025"
    event = expedientes_filing_events(expediente_declaration(remote_ref), snapshot_id="3" * 64)
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            modelo_record(
                aeat_accepted=True,
                external_evidence=external_evidence(
                    ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    local_ref,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
            ),
        ),
        observed_events=event,
        filed_declaration_observations=(
            filed_declaration_observation(
                artefacts=(filed_declaration_artefact(),),
                expediente_id=remote_ref,
            ),
        ),
        verified_filed_declaration_artefact_refs=(FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={FILED_JUSTIFICANTE_STORAGE_REF: verified_csv},
        expected_tax_id="X0001500M",
    )

    calendar = build_overview_calendar(
        profile(),
        OverviewCalendarRange(from_date=date(2025, 4, 1), to_date=date(2025, 4, 30)),
        operation=authority_operation,
        today=date(2025, 4, 10),
        events=event,
        filing_evidence=evidence,
    )

    row = next(
        entry.filing_evidence
        for entry in calendar.entries
        if entry.modelo == "303" and entry.filing_year == 2025 and entry.period == PERIOD_2025_1T
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


def test_calendar_does_not_conflict_live_capture_csv_with_matching_filed_history_csv(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A local live-capture CSV and filed-history expediente can point to the same receipt."""
    csv = "CSVFILED3031T2025"
    expediente_id = "12345678901234567890"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            modelo_record(
                aeat_accepted=True,
                external_evidence=external_evidence(
                    ExternalEvidenceKind.AEAT_LIVE_CAPTURE,
                    csv,
                    imported_at=datetime(2025, 4, 16, 12, 0, tzinfo=UTC),
                ),
            ),
        ),
        filed_declaration_observations=(
            filed_declaration_observation(
                artefacts=(filed_declaration_artefact(),),
                expediente_id=expediente_id,
            ),
        ),
        verified_filed_declaration_artefact_refs=(FILED_JUSTIFICANTE_STORAGE_REF,),
        verified_filed_declaration_artefact_csvs={FILED_JUSTIFICANTE_STORAGE_REF: csv},
        expected_tax_id="X0001500M",
    )

    calendar, row = _april_2025_303_filing_row(evidence, authority_operation)
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.verified_justificante_csv == csv
    assert row.aeat_evidence_conflict_reference_ids == ()
    assert "filing.aeat_evidence_conflict" not in {warning.code for warning in calendar.warnings}


def test_calendar_does_not_conflict_matching_verified_csv_across_reference_namespaces(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """CSV-backed local evidence and expediente-backed filed-history evidence can describe the same receipt."""
    csv = "JUST3032025X1T7"
    expediente_id = "12345678901234567890"
    payload = calculation_observation_payload(
        source_kind="aeat_sede_justificante",
        source_metadata={
            "aeat_register_status": "ALTA",
            "aeat_expediente_id": expediente_id,
            "aeat_justificante_csv": csv,
            "authenticated_identity": "X0001500M",
        },
    )
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            modelo_record(
                aeat_accepted=True,
                external_evidence=external_evidence(
                    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    csv,
                    imported_at=datetime(2025, 4, 16, 11, 0, tzinfo=UTC),
                ),
                filed_by="aeat-import",
            ),
        ),
        calculation_observations=(payload,),
        justificantes=(justificante_metadata(csv=csv),),
        expected_tax_id="X0001500M",
    )

    calendar, row = _april_2025_303_filing_row(evidence, authority_operation)
    assert row.aeat_submission_state is OverviewAeatSubmissionState.JUSTIFICANTE_VERIFIED
    assert row.verified_justificante_csv == csv
    assert row.aeat_evidence_conflict_reference_ids == ()
    assert "filing.aeat_evidence_conflict" not in {warning.code for warning in calendar.warnings}
