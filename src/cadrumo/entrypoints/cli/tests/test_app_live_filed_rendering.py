"""Text rendering tests for live filed-declaration capture reports."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ....application.live import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    IvaCompensationHistoryCaptureReport,
    SourceFiledDataCaptureReport,
)
from ....core import Period
from .._app_live_iva_wallet_payloads import IvaWalletCaptureHistoryResult
from .._app_live_rendering import _filed_capture_lines, _source_filed_capture_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _filed_observation_path(modelo: str, year: int, period: str) -> str:
    return f"filed-declarations/{modelo}-{year}-{period}.json"


def _filing_record_id(modelo: str, year: int, period: str) -> str:
    return f"filing-record-{modelo}-{year}-{period}"


def test_live_filed_pull_text_reports_mode_failures_and_evidence_counts() -> None:
    report = FiledDataCaptureReport(
        output_root="filed-declarations",
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
        output_root="filed-declarations",
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
        output_root="filed-declarations",
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


def test_capture_history_result_names_its_failed_declarations() -> None:
    """A partial capture must not present counts without naming what failed.

    ``IvaCompensationHistoryCaptureReport`` carries the failed-declaration
    count and details plus the observation/artefact/casilla evidence behind its
    counts. The CLI result exposed only the success counters, so a run that
    failed to read some declarations was indistinguishable from a complete one.
    """
    report = IvaCompensationHistoryCaptureReport(
        output_root="live/iva-compensation-history",
        year_from=2023,
        year_to=2024,
        captured_count=5,
        observation_paths=("obs/2023-1T.json", "obs/2023-2T.json"),
        artefact_refs=("artefact:2023-1T",),
        casilla_count=12,
        calculation_observation_count=3,
        calculation_observation_keys=("k1", "k2", "k3"),
        reloaded_history_count=2,
        reloaded_rows=(),
        failed_declaration_count=1,
        failed_declarations=("303-2024-2T: read timed out",),
    )

    result = IvaWalletCaptureHistoryResult(
        output_root=report.output_root,
        year_from=report.year_from,
        year_to=report.year_to,
        captured_count=report.captured_count,
        calculation_observation_count=report.calculation_observation_count,
        reloaded_history_count=report.reloaded_history_count,
        casilla_count=report.casilla_count,
        observation_paths=list(report.observation_paths),
        artefact_refs=list(report.artefact_refs),
        calculation_observation_keys=list(report.calculation_observation_keys),
        failed_declaration_count=report.failed_declaration_count,
        failed_declarations=list(report.failed_declarations),
    )

    rendered = json.loads(result.model_dump_json())
    # `reloaded_rows` is deliberately not projected here: its operator surface
    # is the sibling `iva-wallet history` verb, and `reloaded_history_count`
    # already reports its cardinality on this result.
    expected = set(report.model_dump()) - {"reloaded_rows"}
    assert expected - set(rendered) == set()
    assert rendered["failed_declaration_count"] == 1
    assert rendered["failed_declarations"] == ["303-2024-2T: read timed out"]

    assert IvaWalletCaptureHistoryResult.model_validate_json(result.model_dump_json()) == result


def test_capture_history_result_refuses_a_failure_count_without_its_names() -> None:
    """A bare failure number would reinstate the defect the named list closes."""
    with pytest.raises(ValidationError, match="failed_declaration_count"):
        IvaWalletCaptureHistoryResult(
            output_root="live/iva-compensation-history",
            year_from=2024,
            year_to=2024,
            captured_count=0,
            calculation_observation_count=0,
            reloaded_history_count=0,
            failed_declaration_count=3,
            failed_declarations=["303-2024-2T: read timed out"],
        )
