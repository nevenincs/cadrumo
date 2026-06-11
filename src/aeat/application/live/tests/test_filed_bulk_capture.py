"""Tests for bulk filed-declaration capture report models."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....adapters.outbound.aeat.sede import Declaracion
from .. import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
    capture_filed_data_bulk,
    filed_data_capture_failure_row,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _declaration() -> Declaracion:
    return Declaracion(
        modelo="303",
        ejercicio=2025,
        period="1T",
        expediente_id="12345678901234567890",
        estado="ALTA",
        presented_at=datetime(2025, 4, 15, 9, 30, tzinfo=UTC),
    )


def test_bulk_failure_row_preserves_declaration_coordinates() -> None:
    row = filed_data_capture_failure_row(
        modelo="303",
        year=2025,
        declaration=_declaration(),
        error=ValueError("AEAT row did not expose a justificante link"),
    )

    assert row == FiledDataCaptureFailureRow(
        modelo="303",
        year=2025,
        period="1T",
        expediente_id="12345678901234567890",
        error_type="ValueError",
        message="AEAT row did not expose a justificante link",
    )


def test_bulk_report_counts_successes_and_failures_explicitly() -> None:
    failure = filed_data_capture_failure_row(
        modelo="130",
        year=2025,
        error=RuntimeError("modelo not offered by AEAT form"),
    )

    report = BulkFiledDataCaptureReport(
        output_root="var/aeat/filed-declarations",
        modelos=("130", "303"),
        year_from=2025,
        year_to=2025,
        captured_count=1,
        failed_count=1,
        observation_paths=("303/2025/1T/manifest.json",),
        artefact_refs=("sha256:abc123",),
        casilla_count=12,
        calculation_observation_count=1,
        calculation_observation_keys=("303:2025:1T",),
        failures=(failure,),
    )

    assert report.modelos == ("130", "303")
    assert report.captured_count == 1
    assert report.failed_count == 1
    assert report.failures[0].modelo == "130"


def test_bulk_capture_reports_registry_unsupported_modelos_as_local_boundaries(tmp_path: Path) -> None:
    report = asyncio.run(
        capture_filed_data_bulk(
            year_from=2024,
            year_to=2024,
            output_root=tmp_path,
            modelos=("151", "721"),
        ),
    )

    assert report.modelos == ("151", "721")
    assert report.captured_count == 0
    assert report.failed_count == 2
    failures = {failure.modelo: failure for failure in report.failures}
    assert set(failures) == {"151", "721"}
    assert failures["151"].year == 2024
    assert failures["151"].error_type == "LiveApplicationInputError"
    assert "declares no filed-declarations live read surface" in failures["151"].message
    assert failures["721"].year == 2024
    assert failures["721"].error_type == "LiveApplicationInputError"
    assert "does not offer modelo '721'" in failures["721"].message
