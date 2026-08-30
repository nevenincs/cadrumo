"""Filed-declaration evidence coverage for overview calendar filing state."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.period import Period
from ....domain.modelos.filing_record import ExternalEvidenceKind
from ..calendar_evidence import calendar_filing_evidence_from_sources
from ..calendar_models import OverviewAeatSubmissionState, OverviewLocalFilingState
from .calendar_test_support import (
    FILED_JUSTIFICANTE_STORAGE_REF as _FILED_JUSTIFICANTE_STORAGE_REF,
)
from .calendar_test_support import (
    PERIOD_2025_1T as _PERIOD_2025_1T,
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

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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
            ).model_copy(update={"authenticated_identity": "Y7654321G"}),
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
    csv = "JUST3032025X1T7"
    evidence = calendar_filing_evidence_from_sources(
        filing_records=(
            _modelo_record(
                aeat_accepted=True,
                external_evidence=_external_evidence(
                    ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
                    csv,
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


def test_imported_justificante_record_for_nonmatching_receipt_metadata_is_not_verified() -> None:
    csv = "JUST3032025X1T7"
    cases = (
        ("wrong-taxpayer", "303", 2025, _PERIOD_2025_1T, "Y7654321G"),
        ("wrong-modelo", "130", 2025, _PERIOD_2025_1T, "X1234567L"),
        ("wrong-ejercicio", "303", 2024, _PERIOD_2025_1T, "X1234567L"),
        ("wrong-period", "303", 2025, Period.from_year_and_code(2025, "2T"), "X1234567L"),
    )

    for case_id, modelo, filing_year, period, tax_id in cases:
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
            justificantes=(
                _justificante_metadata(
                    csv=csv,
                    modelo=modelo,
                    filing_year=filing_year,
                    period=period,
                    tax_id=tax_id,
                ),
            ),
            expected_tax_id="X1234567L",
        )

        row = evidence[0]
        assert row.local_filing_state is OverviewLocalFilingState.EXTERNAL_BASELINE_IMPORTED, case_id
        assert row.aeat_submission_state is OverviewAeatSubmissionState.ACCEPTED, case_id
        assert row.aeat_evidence_kind == "aeat_justificante_pdf", case_id
        assert row.justificante_verified is False, case_id
