"""Text rendering tests for live filed-declaration capture reports."""

from __future__ import annotations

import pytest

from ....application.live import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from ....core import Period
from .._app_live_rendering import _filed_capture_lines, _source_filed_capture_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _filed_observation_path(modelo: str, year: int, period: str) -> str:
    return f"var/aeat/filed-declarations/{modelo}-{year}-{period}.json"


def _filing_record_id(modelo: str, year: int, period: str) -> str:
    return f"filing-record-{modelo}-{year}-{period}"


def test_live_filed_pull_text_reports_mode_failures_and_evidence_counts() -> None:
    report = FiledDataCaptureReport(
        output_root="var/aeat/filed-declarations",
        modelo="303",
        year=2026,
        captured_count=1,
        observation_paths=(_filed_observation_path("303", 2026, "1T"),),
        artefact_refs=("secure-object:financial:" + "a" * 64,),
        justificante_metadata_count=1,
        justificante_csvs=("CSV30320261T",),
        filing_evidence_stamped_count=1,
        filing_record_ids=(_filing_record_id("303", 2026, "1T"),),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=12,
        calculation_observation_count=1,
        calculation_observation_keys=("303:2026:1T:12345678901234567890",),
    )

    lines = _filed_capture_lines(report, mode="single", modelo=report.modelo, year=report.year)

    assert "mode=single" in lines
    assert "modelo=303" in lines
    assert "year=2026" in lines
    assert "failed_count=0" in lines
    assert "justificante_metadata_count=1" in lines
    assert "justificante_csvs=CSV30320261T" in lines
    assert "filing_evidence_stamped_count=1" in lines
    assert f"filing_record_ids={_filing_record_id('303', 2026, '1T')}" in lines


def test_live_filed_bulk_pull_text_reports_failures_without_pull_all() -> None:
    failure = FiledDataCaptureFailureRow(
        modelo="303",
        year=2026,
        period=Period.from_year_and_code(2026, "2T"),
        expediente_id="202620013522222B",
        error_type="ValueError",
        message="bounded register timeout",
    )
    report = BulkFiledDataCaptureReport(
        output_root="var/aeat/filed-declarations",
        modelos=("303", "390"),
        year_from=2026,
        year_to=2026,
        captured_count=0,
        failed_count=1,
        observation_paths=(),
        artefact_refs=(),
        justificante_metadata_count=0,
        justificante_csvs=(),
        filing_evidence_stamped_count=0,
        filing_record_ids=(),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=0,
        calculation_observation_count=0,
        calculation_observation_keys=(),
        failures=(failure,),
    )

    lines = _filed_capture_lines(
        report,
        mode="bulk",
        modelos=report.modelos,
        year_from=report.year_from,
        year_to=report.year_to,
        failures=report.failures,
    )

    assert "mode=bulk" in lines
    assert "modelo_count=2" in lines
    assert "year_from=2026" in lines
    assert "year_to=2026" in lines
    assert "failed_count=1" in lines
    assert any(line.startswith("failure=303\t2026\t2T\t202620013522222B\tValueError\t") for line in lines)


def test_live_filed_pull_sources_text_reports_target_period_and_evidence_counts() -> None:
    report = SourceFiledDataCaptureReport(
        output_root="var/aeat/filed-declarations",
        target_modelo="130",
        target_year=2026,
        target_period=Period.from_year_and_code(2026, "1T"),
        captured_count=2,
        observation_paths=(
            _filed_observation_path("130", 2026, "1T"),
            _filed_observation_path("100", 2025, "0A"),
        ),
        artefact_refs=("secure-object:financial:" + "b" * 64,),
        justificante_metadata_count=1,
        justificante_csvs=("CSV13020261T",),
        filing_evidence_stamped_count=1,
        filing_record_ids=(_filing_record_id("130", 2026, "1T"),),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=18,
        calculation_observation_count=2,
        calculation_observation_keys=("130:2026:1T:EXP", "100:2025:0A:EXP"),
    )

    lines = _source_filed_capture_lines(report)

    assert "target_modelo=130" in lines
    assert "target_year=2026" in lines
    assert "target_period=1T" in lines
    assert "mode=sources" in lines
    assert "failed_count=0" in lines
    assert "captured_count=2" in lines
    assert "justificante_metadata_count=1" in lines
    assert "filing_evidence_stamped_count=1" in lines
