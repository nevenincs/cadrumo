"""A statement import whose reader needs the local AI settles with the setup verdict on that file.

The registered ``ledger.import`` runs through the production registry, the real
supervisor, journal and encrypted operand store, and the column-naming and
statement readers the profile adapter composition binds, against a real
loopback runtime that answers its inventory with no model and records every
read it is sent. The result is then read back the way a frontend in another
process reads it: as the settled public projection.

One file of a folder can need the local AI while the others import, so the
verdict rides on that file's refusal rather than refusing the operation: the
CSV lane imports a readable statement beside an export only the column-naming
model reads, and the PDF lane refuses a statement only the statement reader
reads. Each refused file must carry the verdict naming the local AI setup, and
no read may be sent to the runtime first. The CLI then renders each settled
result through its real error boundary and live action resolver, with the
local AI's quick-status row the components role reported as absent: the
file's sentence and the exact setup command.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path
from typing import override
from uuid import UUID

import pytest
import typer

from cadrumo.tests.english_locale_fixture import english_locale_fixture
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion

from ....adapters.outbound.components.tests.recorded_rows import recorded_absent_row
from ....adapters.outbound.llm.column_role_mapping import resolve_column_roles
from ....adapters.outbound.llm.statement_reading import LocalStatementReader
from ....application.dependency_contracts import DependencyStatusRow
from ....application.dependency_registry import dependency_item_declarations
from ....application.ledger.actions_import import LedgerProviderID
from ....application.ledger.column_roles import bind_column_role_mapping_resolver
from ....application.ledger.import_operation import (
    LEDGER_IMPORT_OPERATION_DEFINITION_ID,
    LedgerImportFileRefusal,
    LedgerImportRequest,
    LedgerImportResultProjection,
)
from ....application.ledger.statement_reading import bind_statement_reader_factory
from ....application.operations.frontend_requests import OperationObservationSuccessV1
from ....application.operations.registry import OperationRegistry
from ....application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ....core.config import override_settings
from ....core.model_catalogue import ModelRole, candidates_for_role, default_model_runtime_id
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.inventory import FIXTURES_DIR
from ....tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...tests import registered_executor_case_support as conformance
from .. import ledger_import_commands
from .._component_setup_rendering import setup_status_source
from ..errors import command_error_boundary
from .cli_runner import invoke_typer_app, semantic_cli_output

__all__ = ["english_locale_fixture"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

#: An expenses-app export whose header vocabulary no exact provider reads, so only the column-naming model reads it.
_UNKNOWN_FORMAT_EXPORT = FIXTURES_DIR / "financial" / "tabular-dialects" / "expenses_app_export_2026.csv"
#: A text-layer PDF statement, which only the statement reader reads.
_PDF_STATEMENT = FIXTURES_DIR / "financial" / "n26" / "n26-savings-2025-01.pdf"
_READABLE_STATEMENT = (
    "Fecha operación;Fecha valor;Concepto;Importe;Saldo;Moneda\n"
    "08/04/2026;08/04/2026;Transferencia recibida CLIENTE UNO;1500,25;4300,75;EUR\n"
)

#: An operator-named mapping model. The catalogue's own choice is sized to the
#: free memory measured now and can refuse without a setup action on a busy host.
_OPERATOR_MAPPING_MODEL = next(
    candidate.runtime_id
    for candidate in candidates_for_role(ModelRole.COLUMN_ROLE_MAPPING)
    if candidate.runtime_id != default_model_runtime_id(ModelRole.COLUMN_ROLE_MAPPING)
)


@contextmanager
def _production_readers() -> Generator[None]:
    """Bind the column-naming and statement readers exactly as the profile adapter composition does."""
    with bind_column_role_mapping_resolver(resolve_column_roles), bind_statement_reader_factory(LocalStatementReader):
        yield


@contextmanager
def _runtime_holding_nothing(posts: list[str]) -> Generator[None]:
    """Serve a real runtime that answers its inventory with no model and records every read it is sent."""

    class _EmptyRuntime(SilentLoopbackHandler):
        @override
        def do_GET(self) -> None:
            write_json_response(self, {"models": []}, status=HTTPStatus.OK)

        @override
        def do_POST(self) -> None:
            posts.append(self.path)
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)

    with (
        serving_loopback(_EmptyRuntime, path="/api/chat") as chat_url,
        override_settings(
            cadrumo_llm_ollama_chat_url=chat_url, cadrumo_llm_ollama_mapping_model=_OPERATOR_MAPPING_MODEL
        ),
    ):
        yield


def _settle_import(
    driver: conformance._ExecutionDriver,
    registry: OperationRegistry,
    profile_id: UUID,
    *,
    files: tuple[Path, ...],
    provider: LedgerProviderID,
) -> tuple[OperationEffect | None, LedgerImportResultProjection]:
    async def run() -> OperationObservationSuccessV1:
        submitted, _observed = await driver.run(
            definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(profile_id)),
            payload=LedgerImportRequest(profile_id=profile_id, files=files, provider=provider),
        )
        return await driver.observe(submitted.receipt.operation_id)

    observed = asyncio.run(run())
    projection = observed.projection
    assert projection.terminal_condition is OperationTerminalCondition.SUCCEEDED, projection
    result = conformance._resolve_result_projection(
        driver,
        registry,
        definition_id=LEDGER_IMPORT_OPERATION_DEFINITION_ID,
        operation_id=projection.operation_id,
        terminal_revision=projection.revision,
        projection_type=LedgerImportResultProjection,
    )
    return projection.effect, result


_LOCAL_AI_FIX = "To fix it, run: aeat config provision pull"


def _absent_rows() -> tuple[DependencyStatusRow, ...]:
    """Every item's quick-status row as the components role reported it on a root without the item."""
    return tuple(recorded_absent_row(declaration.item_id) for declaration in dependency_item_declarations())


def _cli_import_text(
    monkeypatch: pytest.MonkeyPatch, projection: LedgerImportResultProjection, effect: OperationEffect, named: Path
) -> tuple[int, str]:
    """Render a settled import as the CLI command does, with the runtime submission answering ``projection``."""

    def submit(_ctx: typer.Context, **_options: object) -> RegisteredOperationCompletion[LedgerImportResultProjection]:
        return RegisteredOperationCompletion(operation_id="a" * 64, projection=projection, effect=effect)

    monkeypatch.setattr(ledger_import_commands, "import_ledger_sources_for_cli", submit)
    app = typer.Typer()

    @app.command()
    @command_error_boundary
    def imported(ctx: typer.Context) -> None:
        ledger_import_commands.ledger_import(ctx, named, LedgerProviderID.AUTO)

    with setup_status_source(_absent_rows):
        result = invoke_typer_app(app, [], catch_exceptions=False)
    return result.exit_code, semantic_cli_output(result)


def _assert_names_the_local_ai_setup(refusal: LedgerImportFileRefusal, role: ModelRole) -> None:
    assert refusal.reason_code == "reader_unavailable"
    assert refusal.precondition_verdict is not None, "the settled result lost the reader probe's verdict"
    verdict = refusal.precondition_verdict.to_verdict()
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert {str(item.values.get("role")) for item in verdict.evidence} == {role.value}
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID


def test_a_folder_imports_its_readable_statement_and_names_the_local_ai_for_the_export_it_needs(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    del operation
    folder = tmp_path / "statements"
    folder.mkdir()
    (folder / "a_readable.csv").write_text(_READABLE_STATEMENT, encoding="utf-8")
    (folder / "b_expenses_export.csv").write_bytes(_UNKNOWN_FORMAT_EXPORT.read_bytes())
    posts: list[str] = []
    with (
        _runtime_holding_nothing(posts),
        _production_readers(),
        conformance.conformance_operation_runtime(
            tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
        ) as (driver, registry, profile_id),
    ):
        effect, result = _settle_import(driver, registry, profile_id, files=(folder,), provider=LedgerProviderID.AUTO)

    assert effect is OperationEffect.UPDATED
    assert (result.rows, result.imported) == (1, 1), "the readable statement is imported beside the refused export"
    (refusal,) = result.refused_files
    assert refusal.file_name == "b_expenses_export.csv"
    _assert_names_the_local_ai_setup(refusal, ModelRole.COLUMN_ROLE_MAPPING)
    assert posts == [], "a read was sent before the reader was checked"

    exit_code, text = _cli_import_text(monkeypatch, result, effect, folder)
    assert exit_code == 0, text
    lines = text.splitlines()
    assert "  refused\tb_expenses_export.csv\treader_unavailable" in lines
    assert f"  {_LOCAL_AI_FIX}" in lines


def test_a_pdf_statement_whose_reader_has_no_model_settles_with_the_local_ai_setup(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    del operation
    posts: list[str] = []
    with (
        _runtime_holding_nothing(posts),
        _production_readers(),
        conformance.conformance_operation_runtime(
            tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
        ) as (driver, registry, profile_id),
    ):
        effect, result = _settle_import(
            driver, registry, profile_id, files=(_PDF_STATEMENT,), provider=LedgerProviderID.PDF
        )

    assert effect is OperationEffect.NONE
    assert (result.rows, result.imported, result.validations) == (0, 0, ())
    (refusal,) = result.refused_files
    assert refusal.file_name == _PDF_STATEMENT.name
    _assert_names_the_local_ai_setup(refusal, ModelRole.TEXT_EXTRACTION)
    assert posts == [], "a read was sent before the reader was checked"

    exit_code, text = _cli_import_text(monkeypatch, result, effect, _PDF_STATEMENT)
    assert exit_code != 0
    lines = text.splitlines()
    assert f"Statement not read: {_PDF_STATEMENT.name} is read by the local AI, which is not ready." in lines[0]
    assert lines[-1] == f"  {_LOCAL_AI_FIX}", text
    assert "failed_condition_id" not in text


def test_a_file_refusal_carries_a_verdict_exactly_when_its_reader_was_unavailable() -> None:
    with pytest.raises(ValueError, match="exactly when its reader was unavailable"):
        LedgerImportFileRefusal(file_name="statement.csv", reason_code="reader_unavailable")
