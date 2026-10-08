"""Real registry, composition, and supervision proofs for Google Sheets export."""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
import typer

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from ....application.export.google_operation import (
    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
    GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
    GoogleSheetsExportOperationRequest,
    GoogleSheetsExportPublicResultV1,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
    build_google_sheets_export_service,
)
from ....application.operations.capabilities import OperationRequestStoragePolicy
from ....application.operations.composition import compose_operation_services
from ....application.operations.models import OperationRequest
from ....application.operations.persistence.leases import operation_conflict_scope_reference
from ....application.operations.registry import OperationRegistry
from ....application.operations.tests.authority_test_support import unread_authority_operation
from ....core.operations import (
    OperationEffect,
    OperationEventKind,
    OperationTerminalCondition,
)
from ...operation_composition import compose_operation_dependencies
from .._modelo_spreadsheet_payloads import ModeloSpreadsheetPushResult
from ..errors import CliRefusedBoundaryError
from ..runtime_modelo_spreadsheet_push import google_operation_error

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize(
    ("code", "message_key"),
    (
        ("REFUSED_GOOGLE_SHEETS_EXPORT_CAPABILITY_DISABLED", "cli.app.modelo.spreadsheet.push.capability_disabled"),
        ("REFUSED_GOOGLE_SHEETS_EXPORT_ROOT_FOLDER_REQUIRED", "cli.app.modelo.spreadsheet.push.root_folder_required"),
        (
            "REFUSED_GOOGLE_SHEETS_EXPORT_CLIENT_MISSING",
            "errors.refused.refused_google_client_metadata_unavailable",
        ),
        (
            "REFUSED_GOOGLE_SHEETS_EXPORT_TOKEN_MISSING",
            "adapters.outbound.storage._factory.errors.google_token_missing",
        ),
    ),
)
def test_cli_projects_registered_export_refusals_without_an_owner_allowlist(code: str, message_key: str) -> None:
    projected = google_operation_error(code, diagnostic_ref=None)
    assert isinstance(projected, CliRefusedBoundaryError)
    assert projected.translated_message == message_key


def _services(root: Path, *, definition=None):
    """Compose the actual encrypted supervision stack around the default owner."""
    definition = definition or build_google_sheets_export_operation_definition()
    journal = OperationJournalRepository(storage_root=root)
    leases = OperationLeaseFilesystemRepository(storage_root=root)
    services = compose_operation_services(
        registry=OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_google_sheets_export_operation_registration(definition),),
        ),
        authority_operation=unread_authority_operation(),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=leases,
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=5),
        cleanup_timeout=timedelta(seconds=5),
    )
    return services, journal, leases


async def _submit_and_start(services, journal, request: OperationRequest[GoogleSheetsExportOperationRequest]):
    submission = await services.submission.submit(
        request,
        actor_ref="operator:google-export-test",
        operation_id="a" * 64,
    )
    await services.submission.start(submission.receipt.operation_id)
    await services.submission.settled(submission.receipt.operation_id)
    return await journal.load(submission.receipt.operation_id), await journal.read_after(
        submission.receipt.operation_id, 0, limit=20
    )


def test_google_sheets_export_definition_declares_one_safe_credential_free_contract() -> None:
    definition = build_google_sheets_export_operation_definition()
    registration = build_google_sheets_export_operation_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = GoogleSheetsExportOperationRequest(
        profile_id=UUID("11111111-1111-4111-8111-111111111111"),
        modelo="130",
        filing_year=2025,
        period="1T",
        prefill_relations=True,
        dry_run=True,
    )

    assert GoogleSheetsExportOperationRequest.model_validate_json(request.model_dump_json()) == request
    assert definition.executor_factory.create().__class__.__name__ == "GoogleSheetsExportOperationExecutor"
    assert registry.lookup(GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID).capabilities.request_storage is (
        OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    )
    assert registration.contract.request_schema.schema_id == "export.google-sheets.request"
    assert registration.contract.result_schema is not None
    assert registration.contract.result_schema.schema_id == "export.google-sheets.result"
    request_schema = json.dumps(GoogleSheetsExportOperationRequest.model_json_schema(mode="validation")).lower()
    assert "secret" not in request_schema
    assert "token" not in request_schema


def test_default_owner_builds_a_real_registry_plan_then_refuses_uncomposed_remote_execution(
    tmp_path: Path,
) -> None:
    """No fabricated snapshot, plan, port, mock, or patched transport is used here."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        services, journal, leases = _services(profile.storage_root)
        request = OperationRequest(
            definition_id=GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile.bucket_id}",
            payload=GoogleSheetsExportOperationRequest(
                profile_id=UUID(profile.bucket_id),
                modelo="130",
                filing_year=2025,
                period="1T",
                dry_run=False,
            ),
        )
        try:
            terminal, replay = asyncio.run(_submit_and_start(services, journal, request))
        finally:
            asyncio.run(services.shutdown())

    assert terminal.terminal_condition is OperationTerminalCondition.FAILED
    assert terminal.effect is OperationEffect.NONE
    scope_ref = operation_conflict_scope_reference(
        definition_id=terminal.identity.definition_id,
        subject_ref=terminal.identity.subject_ref,
    )
    released = asyncio.run(leases.inspect(scope_ref, terminal.identity.operation_id, observed_at=datetime.now(UTC)))
    assert released.current is None
    assert tuple(event.phase_code for event in replay.events if event.kind is OperationEventKind.PHASE) == (
        GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
        GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    )


def test_production_composition_registers_the_application_owned_definition_and_real_transport(tmp_path: Path) -> None:
    """The production registry binds this owner to the single outer composition transport."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies(authority_operation=unread_authority_operation())
        try:
            definition = dependencies.observation.registry.lookup(GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID)
            assert definition.executor_factory.create().__class__.__name__ == "GoogleSheetsExportOperationExecutor"
            assert (
                dependencies.observation.registry.lookup_public_contract(
                    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID
                ).request_schema.schema_id
                == "export.google-sheets.request"
            )
        finally:
            asyncio.run(dependencies.shutdown())


def test_google_export_owner_and_composition_keep_one_hexagonal_apply_plus_provenance_route() -> None:
    """The application owner has no adapter dependency; the outer port always calls the provenance service."""
    owner_source = (Path(__file__).parents[3] / "application" / "export" / "google_operation.py").read_text(
        encoding="utf-8"
    )
    owner_tree = ast.parse(owner_source)
    owner_imports = tuple(node.module or "" for node in ast.walk(owner_tree) if isinstance(node, ast.ImportFrom))
    assert not any(module.startswith("adapters") or module.startswith("entrypoints") for module in owner_imports)

    composition_source = (Path(__file__).parents[2] / "operation_composition.py").read_text(encoding="utf-8")
    composition_tree = ast.parse(composition_source)
    direct_calls = {
        node.func.id
        for node in ast.walk(composition_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    provenance_handoffs = [
        node
        for node in ast.walk(composition_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "export_modelo_to_sheets"
    ]
    assert {"export_modelo_to_sheets", "preview_export_plan"}.issubset(direct_calls)
    assert any(
        keyword.arg == "apply_export_plan"
        and isinstance(keyword.value, ast.Name)
        and keyword.value.id == "apply_export_plan"
        for handoff in provenance_handoffs
        for keyword in handoff.keywords
    )
    assert build_google_sheets_export_service().__class__.__name__ == "GoogleSheetsExportService"


def test_cli_push_uses_bound_profile_and_registered_export_contract(monkeypatch) -> None:
    """The CLI forwards its admitted profile and exact request to the registered runtime route."""
    from ....adapters.local_runtime.frontend_client import RuntimeFrontendClient
    from ....application.operations.models import OperationId
    from ....core.operations import profile_operation_subject
    from .. import modelo_spreadsheet_cli as cli_module
    from .. import runtime_modelo_spreadsheet_push as push_runtime
    from ..registered_operation_contracts import RegisteredOperationCompletion

    profile_id = UUID("12345678-1234-4234-8234-123456789abc")
    client = cast(RuntimeFrontendClient, cast(object, SimpleNamespace(profile_id=profile_id)))
    public_result = GoogleSheetsExportPublicResultV1(
        profile_id=profile_id,
        modelo="130",
        revision="r1",
        period="1T",
        filing_year=2025,
        engine_version="test-engine",
        registry_sha="a" * 64,
        dry_run=True,
        root_folder_id="drive-root",
        spreadsheet_exists=False,
        spreadsheet_id=None,
        folder_id=None,
        spreadsheet_url=None,
        value_cells_written=1,
        formula_cells_written=2,
        protected_ranges_written=3,
        tab_count=4,
        ranges_to_clear=("Hoja 1!A1:B2",),
        value_cells_changed=5,
        value_cells_unchanged=6,
        formula_cells_to_write=7,
    )
    completion = RegisteredOperationCompletion[GoogleSheetsExportPublicResultV1](
        operation_id=cast(OperationId, "b" * 64),
        projection=public_result,
        effect=OperationEffect.NONE,
        terminal_condition=OperationTerminalCondition.SUCCEEDED,
    )
    submitted: dict[str, object] = {}
    emitted: dict[str, object] = {}

    def complete(actual_client, request, **kwargs):
        submitted.update(client=actual_client, request=request, **kwargs)
        return completion

    monkeypatch.setattr(push_runtime, "run_registered_operation", complete)
    monkeypatch.setattr(cli_module, "bound_profile_client", lambda _ctx: client)
    monkeypatch.setattr(
        cli_module,
        "emit_envelope",
        lambda _ctx, **kwargs: emitted.update(kwargs),
    )

    cli_context = cast(typer.Context, SimpleNamespace())
    cli_module.modelo_spreadsheet_push(cli_context, "130", "1T", 2025, prefill_relations=True, dry_run=True)

    request = submitted["request"]
    assert submitted["client"] is client
    assert isinstance(request, GoogleSheetsExportOperationRequest)
    assert request.profile_id == profile_id
    assert request.modelo == "130"
    assert request.period == "1T" and request.filing_year == 2025
    assert request.prefill_relations is True and request.dry_run is True
    assert submitted["definition_id"] == GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID
    assert submitted["subject_ref"] == profile_operation_subject(str(profile_id))
    assert submitted["request_version"] == submitted["result_version"] == 1
    assert submitted["timeout"] == 120
    assert emitted["command"] == "modelo.spreadsheet.push"
    result = cast(ModeloSpreadsheetPushResult, emitted["result"])
    assert result.profile == str(profile_id)
    assert result.ranges_to_clear == ["Hoja 1!A1:B2"]
    assert result.formula_cells_to_write == 7
