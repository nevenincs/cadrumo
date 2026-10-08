"""Saved review XLSX is reachable through the actual operator command parser."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import openpyxl
import pytest

from ....application.user_profile.login_session import resolve_login_target
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.calculation_revision import CalculationRevisionState
from ....tests.cli_envelope import unwrap_schema_envelope
from ...tests.modelo_operation_test_support import seeded_modelo_calculation_revision, seeded_modelo_verification_report
from .cli_runner import invoke_cached_cli
from .review_export_native_support import invoke_native_review, native_review_profile
from .runtime_profile_cli_fixture import NativeCliProfileFixture

__all__ = ["native_review_profile"]


@pytest.mark.unit
@pytest.mark.hex_entrypoint
def test_saved_review_command_is_registered_with_exact_selection_and_local_destination() -> None:
    result = invoke_cached_cli(["--language", "en", "app", "modelo", "spreadsheet", "review", "--help"])
    assert result.exit_code == 0, result.output
    assert "--calculation-revision-id" in result.output
    assert "--output" in result.output
    assert "saved draft" in result.output


@pytest.mark.integration
@pytest.mark.hex_entrypoint
@pytest.mark.parametrize("state", [CalculationRevisionState.BORRADOR, CalculationRevisionState.VERIFICADO_COMPLETO])
def test_saved_draft_and_completed_calculations_export_actual_review_workbooks(
    tmp_path: Path,
    state: CalculationRevisionState,
    native_review_profile: NativeCliProfileFixture,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    assert native_review_profile.label is not None
    profile_id = UUID(resolve_login_target(native_review_profile.label).bucket_id)
    if state is CalculationRevisionState.BORRADOR:
        revision_id = seeded_modelo_calculation_revision(profile_id, operation=operation)
    else:
        revision_id, _ = seeded_modelo_verification_report(profile_id, operation=operation)
    output = tmp_path / "saved-review.xlsx"
    result = invoke_native_review(
        native_review_profile,
        [
            "app",
            "modelo",
            "spreadsheet",
            "review",
            "--calculation-revision-id",
            revision_id,
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    publication = unwrap_schema_envelope(result.output)["publication"]
    assert publication["calculation_revision_id"] == revision_id
    assert publication["calculation_state"] == state.value
    assert publication["output_path"] == str(output)
    assert output.is_file()
    workbook = openpyxl.load_workbook(output, data_only=False)
    try:
        assert len(workbook.sheetnames) >= 3
        assert not any(cell.data_type == "f" for sheet in workbook for row in sheet for cell in row)
    finally:
        workbook.close()
    original = output.read_bytes()
    refused = invoke_native_review(
        native_review_profile,
        [
            "app",
            "modelo",
            "spreadsheet",
            "review",
            "--calculation-revision-id",
            revision_id,
            "--output",
            str(output),
        ],
    )
    assert refused.exit_code != 0, refused.output
    assert output.read_bytes() == original
