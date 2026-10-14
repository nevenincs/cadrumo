"""Actual reconciliation export command reaches saved secure records and XLSX publication."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import openpyxl
import pytest
from click.testing import Result

from cadrumo.adapters.inbound.justificante.parser import parse_justificante
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.application.modelo.reconciliation import prepare_parsed_justificante
from cadrumo.application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.entrypoints.cli.tests.modelo_review_package_support import seed_exportable_modelo_revision
from cadrumo.tests.cli_envelope import unwrap_schema_envelope
from cadrumo.tests.inventory import FIXTURES_DIR
from cadrumo_runtime.commands.tests.runtime_profile_cli_fixture import NativeCliProfileFixture

from .review_export_native_support import invoke_native_review, native_review_profile

__all__ = ["native_review_profile"]


@pytest.mark.unit
@pytest.mark.hex_entrypoint
def test_reconciliation_export_help_declares_explicit_saved_selectors(run_cadrumo_cli: Callable[..., Result]) -> None:
    result = run_cadrumo_cli(["--language", "en", "app", "modelo", "reconcile", "export", "--help"])
    assert result.exit_code == 0, result.output
    assert all(option in result.output for option in ("--event-id", "--work-unit-id", "--all-history", "--output"))


@pytest.mark.integration
@pytest.mark.hex_entrypoint
def test_saved_difference_review_exports_through_the_registered_cli(
    tmp_path: Path,
    native_review_profile: NativeCliProfileFixture,
    run_cadrumo_cli: Callable[..., Result],
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    work_id, _ = seed_exportable_modelo_revision(input_values_by_casilla_id={}, operation=operation)
    unit = WorkUnitCatalogueRepository().load().get(work_id)
    assert unit is not None
    source = FIXTURES_DIR / "justificantes" / "modelo_130_2026Q1.pdf"
    prepared = prepare_parsed_justificante(
        work_unit=unit,
        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
        source_ref=str(source),
        actor="synthetic-review-test",
        justificante=parse_justificante(source),
        operation=operation,
    )
    prepared.persist()
    assert prepared.report.diffs
    output = tmp_path / "differences.xlsx"
    result = invoke_native_review(
        native_review_profile,
        [
            "app",
            "modelo",
            "reconcile",
            "export",
            "--event-id",
            prepared.record.bucket_event_id,
            "--output",
            str(output),
        ],
        invoke_cli=run_cadrumo_cli,
    )
    assert result.exit_code == 0, result.output
    publication = unwrap_schema_envelope(result.output)["publication"]
    assert publication["event_id"] == prepared.record.bucket_event_id
    assert publication["difference_count"] == len(prepared.report.diffs)
    workbook = openpyxl.load_workbook(output)
    try:
        strings = [str(cell.value) for sheet in workbook for row in sheet for cell in row if cell.value is not None]
        for difference in prepared.report.diffs:
            assert difference.field_name in strings
            assert difference.work_unit_value in strings
            assert difference.evidence_value in strings
    finally:
        workbook.close()
