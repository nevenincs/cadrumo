"""Cross-period clean-state external evidence reconciliation coverage."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core import Period
from ....domain.justificante import Justificante, JustificanteRepository
from ....domain.modelos import ExternalEvidenceKind, ModeloRecord
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.secure_sql import isolated_runtime_profile
from .. import CrossPeriodCleanStateBlocker
from ._cross_period_clean_state_support import (
    BUCKET_ID as _BUCKET_ID,
)
from ._cross_period_clean_state_support import (
    CLOCK as _CLOCK,
)
from ._cross_period_clean_state_support import (
    external_evidence_blockers as _external_evidence_blockers,
)
from ._cross_period_clean_state_support import (
    live_capture_filing as _live_capture_filing,
)
from ._cross_period_clean_state_support import (
    persist_justificante_metadata as _persist_justificante_metadata,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize(
    ("csv", "expected_tax_id", "mismatch_expected"),
    (
        pytest.param("LIVECAP130MATCH01", "X1234567L", False, id="matching-taxpayer"),
        pytest.param("LIVECAP130NOIDENT", None, True, id="missing-expected-taxpayer"),
        pytest.param("LIVECAP130CASE01", "x1234567l", False, id="case-insensitive-taxpayer"),
    ),
)
def test_live_capture_evidence_reconciles_taxpayer_identity(
    tmp_path: Path,
    csv: str,
    expected_tax_id: str | None,
    mismatch_expected: bool,
) -> None:
    """Live-capture receipt reconciliation requires the expected taxpayer axis."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _external_evidence_blockers(filing, "app_filing", expected_tax_id)

    assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION not in blockers
    assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD not in blockers
    if mismatch_expected:
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers
    else:
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_live_capture_evidence_rejects_mismatched_typed_justificante_period(tmp_path: Path) -> None:
    """A matching ejercicio label cannot override a mismatched typed Period value."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130MISMATCH"
        pdf_bytes = b"%PDF-1.4\n% mismatched period justificante\n%%EOF\n"
        JustificanteRepository().save(
            Justificante(
                csv=csv,
                modelo="130",
                period=Period.from_year_and_code(2025, "1T"),
                ejercicio="2026",
                presentation_id=None,
                presented_at=_CLOCK,
                tax_id="X1234567L",
                total_a_ingresar=None,
                total_a_devolver=None,
                verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
                source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
                source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
                parsed_at=_CLOCK,
            ),
        )
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _external_evidence_blockers(filing, "app_filing")

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_evidence_rejects_mismatched_filed_history_justificante_csv(
    tmp_path: Path,
) -> None:
    """Filed-history metadata cannot point at a different justificante than the filing record."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130CSVLOCK"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            source_metadata={
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_justificante_csv": "OTHER",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


@pytest.mark.parametrize(
    ("csvs_metadata", "mismatch_expected"),
    (
        pytest.param("OTHER,{csv}", False, id="plural-includes-filing-csv"),
        pytest.param("OTHER-ONE,OTHER-TWO", True, id="plural-excludes-filing-csv"),
    ),
)
def test_live_capture_evidence_reconciles_plural_filed_history_justificante_csv(
    tmp_path: Path,
    csvs_metadata: str,
    mismatch_expected: bool,
) -> None:
    """Plural filed-history CSV metadata must not bypass reference reconciliation."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130CSVSET"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            source_metadata={
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_justificante_csvs": csvs_metadata.format(csv=csv),
            },
        )

    if mismatch_expected:
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers
    else:
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_live_capture_evidence_rejects_mismatched_filed_history_presentation_id(
    tmp_path: Path,
) -> None:
    """When AEAT exposes both references, expediente and justificante presentation id must agree."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130PRESID"
        period = Period.from_year_and_code(2026, "1T")
        _persist_justificante_metadata(
            csv,
            modelo="130",
            period=period.registry_token,
            filing_year=period.year,
            presentation_id=f"PRES-130-{period.year}-{period.registry_token}",
        )
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            source_metadata={
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_expediente_id": "DIFFERENT-PRESENTATION-ID",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_live_capture_evidence_rejects_expediente_only_metadata_without_comparable_receipt_reference(
    tmp_path: Path,
) -> None:
    """Expediente-only filed history cannot verify a receipt lacking presentation id."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "LIVECAP130EXPONLY"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026, presentation_id=None)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)

        blockers = _external_evidence_blockers(
            filing,
            "aeat_sede_justificante",
            source_metadata={
                "aeat_register_status": "ALTA",
                "authenticated_identity": "X1234567L",
                "aeat_expediente_id": "EXPEDIENTE-WITHOUT-CSV-REFERENCE",
            },
        )

        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD in blockers


def test_csv_register_evidence_clears_with_matching_justificante_metadata(tmp_path: Path) -> None:
    """A CSV-register reference clears the gate only when its justificante is enrolled."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        csv = "CSVREG130ABCD01"
        _persist_justificante_metadata(csv, modelo="130", period="1T", filing_year=2026)
        filing = _live_capture_filing(csv=csv, kind=ExternalEvidenceKind.AEAT_CSV_REGISTER)

        blockers = _external_evidence_blockers(filing, "aeat_csv_register")

        assert CrossPeriodCleanStateBlocker.MISSING_JUSTIFICANTE_VERIFICATION not in blockers
        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD not in blockers
        assert CrossPeriodCleanStateBlocker.MISMATCHED_EXTERNAL_EVIDENCE_RECORD not in blockers


def test_csv_register_evidence_without_enrolled_justificante_still_blocks(tmp_path: Path) -> None:
    """A CSV-register reference without its parsed receipt cannot clear clean-state."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        filing = _live_capture_filing(csv="CSVREG130NOJUST", kind=ExternalEvidenceKind.AEAT_CSV_REGISTER)

        blockers = _external_evidence_blockers(filing, "aeat_csv_register")

        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE_RECORD in blockers


def test_bare_aeat_acceptance_without_external_evidence_does_not_clear_cross_period_gate(tmp_path: Path) -> None:
    """A bare acceptance bit is not enough without an AEAT evidence reference."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        base = _live_capture_filing(csv="LIVECAP130BARE01", kind=ExternalEvidenceKind.AEAT_LIVE_CAPTURE)
        payload_without_external_evidence = base.model_dump(mode="python")
        payload_without_external_evidence["external_evidence"] = None
        filing = ModeloRecord.model_construct(**payload_without_external_evidence)

        blockers = _external_evidence_blockers(filing, "app_filing")

        assert CrossPeriodCleanStateBlocker.MISSING_EXTERNAL_EVIDENCE in blockers
        assert CrossPeriodCleanStateBlocker.LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE in blockers
