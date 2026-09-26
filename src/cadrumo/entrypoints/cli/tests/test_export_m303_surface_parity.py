"""One verified Modelo 303 revision meets the same export gate from either surface.

The command line and the supervised operation the TUI submits both reach the
export service. The operation once forwarded none of the elections the command
line supplies, so a Modelo 303 export through it failed at the missing
prior-domiciliation election, before the gate the command line reached. Both
now carry the same elections, so both reach the missing reviewed product
identity, which every official Modelo 303 envelope requires.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests.modelo_export_support import isolated_backend_context
from cadrumo.application.modelo.operation_definitions import MODELO_EXPORT_OPERATION_DEFINITION_ID, ModeloExportRequest
from cadrumo.application.operations.frontend_requests import (
    OperationObservationRequestV1,
    OperationObservationSuccessV1,
)
from cadrumo.application.operations.models import OperationRequest
from cadrumo.core.operations import OperationTerminalCondition
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli
from cadrumo.entrypoints.operation_composition import compose_operation_dependencies
from cadrumo.entrypoints.tests.profile_persistence.modelo_303_export_support import build_verified_modelo_303_revision

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _export_through_the_operation(
    *, work_unit_id: str, calculation_revision_id: str, output_path: Path, operation: PinnedAuthorityOperation
) -> tuple[OperationTerminalCondition | None, str | None]:
    """Submit the registered export operation with its default elections, as the TUI does."""

    async def run() -> tuple[OperationTerminalCondition | None, str | None]:
        services = compose_operation_dependencies(authority_operation=operation)
        try:
            submitted = await services.submission.submit(
                OperationRequest(
                    definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
                    subject_ref=work_unit_id,
                    payload=ModeloExportRequest(
                        calculation_revision_id=calculation_revision_id,
                        output_path=str(output_path),
                        actor="operator",
                    ),
                ),
                actor_ref="operator:export-parity",
            )
            await services.submission.start(submitted.receipt.operation_id)
            await services.submission.settled(submitted.receipt.operation_id)
            observed = await services.observation.observe(
                OperationObservationRequestV1(
                    operation_id=submitted.receipt.operation_id, after_cursor=0, page_limit=64
                )
            )
            assert isinstance(observed, OperationObservationSuccessV1)
            projection = observed.projection
            return projection.terminal_condition, projection.refusal_ref or projection.failure_error_code
        finally:
            await services.shutdown()

    return asyncio.run(run())


def test_a_modelo_303_revision_exports_identical_bytes_on_both_surfaces(tmp_path: Path) -> None:
    """Both surfaces clear the election precondition and write the same DP30300 envelope."""
    with isolated_backend_context(tmp_path), bundled_indexed_authority().operation() as operation:
        _taxpayer_nif, _bucket_id, verified, *_repositories = build_verified_modelo_303_revision(operation=operation)
        cli_out = tmp_path / "cli-303.txt"
        operation_out = tmp_path / "operation-303.txt"

        cli = invoke_cached_cli(
            [
                "--format",
                "json",
                "app",
                "modelo",
                "export",
                "--revision",
                verified.calculation_revision_id,
                "--output",
                str(cli_out),
            ]
        )
        condition, operation_code = _export_through_the_operation(
            work_unit_id=verified.work_unit_id,
            calculation_revision_id=verified.calculation_revision_id,
            output_path=operation_out,
            operation=operation,
        )

    assert cli.exit_code == 0, cli.output
    assert json.loads(cli.output)["result"]["software_identity_grade"] == "development_mock"
    assert condition is OperationTerminalCondition.SUCCEEDED, operation_code
    assert cli_out.read_bytes() == operation_out.read_bytes()
