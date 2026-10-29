"""A statement import whose reader cannot be run settles with the refused run's verdict on that file.

The registered ``ledger.import`` runs through the production registry, the real
supervisor, journal and encrypted operand store, and the column-naming and
statement readers the profile adapter composition binds. The readers reach a
recording stand-in for the agent service through the operation's execution
authority, as they reach the runtime host; the service refuses every lookup
with one refusal code and records every run it is sent. The result is then read
back the way a frontend in another process reads it: as the settled public
projection.

One file of a folder can need a model while the others import, so the
verdict rides on that file's refusal rather than refusing the operation: the
CSV lane imports a readable statement beside an export only the column-naming
model reads, and the PDF lane refuses a statement only the statement reader
reads. A selected model that is not installed and a role with no selection each
carry their typed verdict naming no action. No run may be sent first. The CLI then renders each settled
result through its real error boundary and live action resolver, with the
file's sentence and the typed facts already carried by the refusal.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from contextlib import contextmanager
from functools import partial
from pathlib import Path
from uuid import UUID

import pytest
import typer

from cadrumo.tests.english_locale_fixture import english_locale_fixture
from cadrumo_client.commands.registered_operation_contracts import RegisteredOperationCompletion
from cadrumo_client.contracts.model_runs import ModelRunRefusal, ModelRunRefusalCode

from ....adapters.outbound.llm.column_role_mapping import resolve_column_roles
from ....adapters.outbound.llm.providers.agent import model_run_refusal_verdict
from ....adapters.outbound.llm.statement_reading import StatementReader
from ....adapters.outbound.llm.tests.model_run_support import RecordingModelRuns
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
from ....core.model_roles import ModelRole
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....tests.inventory import FIXTURES_DIR
from ...tests import registered_executor_case_support as conformance
from ...tests.dependency_operation_gating_support import RecordingRunsAuthority, agent_refusing
from .. import ledger_import_commands
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


@contextmanager
def _production_readers() -> Generator[None]:
    """Bind the column-naming and statement readers exactly as the profile adapter composition does."""
    with bind_column_role_mapping_resolver(resolve_column_roles), bind_statement_reader_factory(StatementReader):
        yield


@contextmanager
def _agent_refusing(code: ModelRunRefusalCode) -> Generator[RecordingModelRuns]:
    """Run operations against an agent service refusing every lookup with ``code``."""
    with agent_refusing(code) as service, pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            conformance,
            "compose_operation_services",
            partial(conformance.compose_operation_services, execution_authority=RecordingRunsAuthority(service)),
        )
        yield service


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

    result = invoke_typer_app(app, [], catch_exceptions=False)
    return result.exit_code, semantic_cli_output(result)


def _assert_carries_the_refusal(refusal: LedgerImportFileRefusal, role: ModelRole, code: ModelRunRefusalCode) -> None:
    assert refusal.reason_code == "reader_unavailable"
    assert refusal.precondition_verdict is not None, "the settled result lost the refused run's verdict"
    verdict = refusal.precondition_verdict.to_verdict()
    assert verdict == model_run_refusal_verdict(ModelRunRefusal(code=code), role=role)
    assert {str(item.values.get("role")) for item in verdict.evidence} == {role.value}


def _assert_names_no_action(refusal: LedgerImportFileRefusal, role: ModelRole) -> None:
    _assert_carries_the_refusal(refusal, role, ModelRunRefusalCode.MODEL_NOT_INSTALLED)
    assert refusal.precondition_verdict is not None
    assert refusal.precondition_verdict.to_verdict().action is None


def test_a_folder_imports_its_readable_statement_and_refuses_the_export_it_needs_a_model_for(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    del operation
    folder = tmp_path / "statements"
    folder.mkdir()
    (folder / "a_readable.csv").write_text(_READABLE_STATEMENT, encoding="utf-8")
    (folder / "b_expenses_export.csv").write_bytes(_UNKNOWN_FORMAT_EXPORT.read_bytes())
    with (
        _agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as service,
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
    _assert_names_no_action(refusal, ModelRole.COLUMN_ROLE_MAPPING)
    assert service.runs == [], "a run was sent although the lookup refused"

    exit_code, text = _cli_import_text(monkeypatch, result, effect, folder)
    assert exit_code == 0, text
    lines = text.splitlines()
    assert "  refused\tb_expenses_export.csv\treader_unavailable" in lines
    assert not any("desktop" in line.lower() for line in lines)


def test_a_pdf_statement_whose_reader_model_is_not_installed_settles_with_its_refusal_verdict(
    tmp_path: Path, operation: PinnedAuthorityOperation, monkeypatch: pytest.MonkeyPatch
) -> None:
    del operation
    with (
        _agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as service,
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
    _assert_names_no_action(refusal, ModelRole.TEXT_EXTRACTION)
    assert service.runs == [], "a run was sent although the lookup refused"

    exit_code, text = _cli_import_text(monkeypatch, result, effect, _PDF_STATEMENT)
    assert exit_code != 0
    lines = text.splitlines()
    assert (
        "Refused. Statement not read: the model you picked is not available right now to read "
        f"{_PDF_STATEMENT.name}. Try again once it is available."
    ) in lines
    assert "desktop" not in text.lower()


def test_an_export_whose_role_has_no_selection_settles_with_its_typed_refusal(
    tmp_path: Path, operation: PinnedAuthorityOperation
) -> None:
    del operation
    folder = tmp_path / "statements"
    folder.mkdir()
    (folder / "b_expenses_export.csv").write_bytes(_UNKNOWN_FORMAT_EXPORT.read_bytes())
    with (
        _agent_refusing(ModelRunRefusalCode.NO_SELECTION) as service,
        _production_readers(),
        conformance.conformance_operation_runtime(
            tmp_path / "runtime", cleanup=conformance.OperationRuntimeCloseWitness()
        ) as (driver, registry, profile_id),
    ):
        _effect, result = _settle_import(driver, registry, profile_id, files=(folder,), provider=LedgerProviderID.AUTO)

    (refusal,) = result.refused_files
    _assert_carries_the_refusal(refusal, ModelRole.COLUMN_ROLE_MAPPING, ModelRunRefusalCode.NO_SELECTION)
    assert refusal.precondition_verdict is not None
    verdict = refusal.precondition_verdict.to_verdict()
    assert verdict.action is None, "no selection action is registered, so none is named"
    assert verdict.evidence[0].values["role_selection_required"] is True
    assert service.runs == []


def test_a_file_refusal_carries_a_verdict_exactly_when_its_reader_was_unavailable() -> None:
    with pytest.raises(ValueError, match="exactly when its reader was unavailable"):
        LedgerImportFileRefusal(file_name="statement.csv", reason_code="reader_unavailable")
