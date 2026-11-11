"""Text rendering tests for live filed-declaration capture reports."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ....application.live.remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledCapturePairOutcome,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    IvaCompensationHistoryCaptureReport,
    SourceFiledDataCaptureReport,
)
from ....core.period import Period
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..app_live_iva_wallet_results import IvaWalletCaptureHistoryResult
from ..app_live_rendering import filed_capture_lines, source_filed_capture_lines

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

YEAR = filing_year_envelope().horizon
OTHER_YEAR = filing_year_envelope().floor
FIRST_YEAR, SECOND_YEAR = filing_year_envelope().years[:2]


def _filed_observation_path(modelo: str, year: int, period: str) -> str:
    return f"filed-declarations/{modelo}-{year}-{period}.json"


def _filing_record_id(modelo: str, year: int, period: str) -> str:
    return f"filing-record-{modelo}-{year}-{period}"


def test_live_filed_pull_text_reports_mode_failures_and_evidence_counts() -> None:
    report = FiledDataCaptureReport(
        output_root="filed-declarations",
        modelo="303",
        year=YEAR,
        captured_count=1,
        observation_paths=(_filed_observation_path("303", YEAR, "1T"),),
        artefact_refs=("secure-object:financial:" + "a" * 64,),
        justificante_metadata_count=1,
        justificante_csvs=(f"CSV303{YEAR}1T",),
        filing_evidence_stamped_count=1,
        filing_record_ids=(_filing_record_id("303", YEAR, "1T"),),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=12,
        calculation_observation_count=1,
        calculation_observation_keys=(f"303:{YEAR}:1T:12345678901234567890",),
    )

    lines = filed_capture_lines(report, mode="single", modelo=report.modelo, year=report.year)

    assert "mode=single" in lines
    assert "modelo=303" in lines
    assert f"year={YEAR}" in lines
    assert "failed_count=0" in lines
    assert "justificante_metadata_count=1" in lines
    assert f"justificante_csvs=CSV303{YEAR}1T" in lines
    assert "filing_evidence_stamped_count=1" in lines
    assert f"filing_record_ids={_filing_record_id('303', YEAR, '1T')}" in lines


def test_live_filed_bulk_pull_text_reports_failures_without_pull_all() -> None:
    failure = FiledDataCaptureFailureRow(
        modelo="303",
        year=YEAR,
        period=Period.from_year_and_code(YEAR, "2T"),
        expediente_id=f"{YEAR}20013522222B",
        error_type="ValueError",
        message="bounded register timeout",
    )
    report = BulkFiledDataCaptureReport(
        pair_outcomes=(
            FiledCapturePairOutcome(
                modelo="303",
                year=YEAR,
                walk_attempted=True,
                walk_completed=False,
                row_count=0,
                reached_count=0,
                captured_count=0,
            ),
            FiledCapturePairOutcome(
                modelo="390",
                year=YEAR,
                walk_attempted=False,
                walk_completed=False,
                row_count=0,
                reached_count=0,
                captured_count=0,
            ),
        ),
        output_root="filed-declarations",
        modelos=("303", "390"),
        year_from=YEAR,
        year_to=YEAR,
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

    lines = filed_capture_lines(
        report,
        mode="bulk",
        modelos=report.modelos,
        year_from=report.year_from,
        year_to=report.year_to,
        failures=report.failures,
    )

    assert "mode=bulk" in lines
    assert "modelo_count=2" in lines
    assert f"year_from={YEAR}" in lines
    assert f"year_to={YEAR}" in lines
    assert "failed_count=1" in lines
    assert "pair_count=2" in lines
    assert any(
        f"303\t{YEAR}" in line and "walk_attempted=True" in line and "walk_completed=False" in line for line in lines
    )
    assert any(
        f"390\t{YEAR}" in line and "walk_attempted=False" in line and "walk_completed=False" in line for line in lines
    )
    assert any(line.startswith(f"failure=303\t{YEAR}\t2T\t{YEAR}20013522222B\tValueError\t") for line in lines)


def test_live_filed_pull_sources_text_reports_target_period_and_evidence_counts() -> None:
    report = SourceFiledDataCaptureReport(
        output_root="filed-declarations",
        target_modelo="130",
        target_year=YEAR,
        target_period=Period.from_year_and_code(YEAR, "1T"),
        captured_count=2,
        observation_paths=(
            _filed_observation_path("130", YEAR, "1T"),
            _filed_observation_path("100", OTHER_YEAR, "0A"),
        ),
        artefact_refs=("secure-object:financial:" + "b" * 64,),
        justificante_metadata_count=1,
        justificante_csvs=(f"CSV130{YEAR}1T",),
        filing_evidence_stamped_count=1,
        filing_record_ids=(_filing_record_id("130", YEAR, "1T"),),
        filing_evidence_conflict_count=0,
        filing_evidence_conflict_record_ids=(),
        casilla_count=18,
        calculation_observation_count=2,
        calculation_observation_keys=(f"130:{YEAR}:1T:EXP", f"100:{OTHER_YEAR}:0A:EXP"),
    )

    lines = source_filed_capture_lines(report)

    assert "target_modelo=130" in lines
    assert f"target_year={YEAR}" in lines
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
        year_from=FIRST_YEAR,
        year_to=SECOND_YEAR,
        captured_count=5,
        observation_paths=(f"obs/{FIRST_YEAR}-1T.json", f"obs/{FIRST_YEAR}-2T.json"),
        artefact_refs=(f"artefact:{FIRST_YEAR}-1T",),
        casilla_count=12,
        calculation_observation_count=3,
        calculation_observation_keys=("k1", "k2", "k3"),
        reloaded_history_count=2,
        reloaded_rows=(),
        failed_declaration_count=1,
        failed_declarations=(f"303-{SECOND_YEAR}-2T: read timed out",),
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
    assert rendered["failed_declarations"] == [f"303-{SECOND_YEAR}-2T: read timed out"]

    assert IvaWalletCaptureHistoryResult.model_validate_json(result.model_dump_json()) == result


def test_capture_history_result_refuses_a_failure_count_without_its_names() -> None:
    """A bare failure number would reinstate the defect the named list closes."""
    with pytest.raises(ValidationError, match="failed_declaration_count"):
        IvaWalletCaptureHistoryResult(
            output_root="live/iva-compensation-history",
            year_from=SECOND_YEAR,
            year_to=SECOND_YEAR,
            captured_count=0,
            calculation_observation_count=0,
            reloaded_history_count=0,
            failed_declaration_count=3,
            failed_declarations=[f"303-{SECOND_YEAR}-2T: read timed out"],
        )
