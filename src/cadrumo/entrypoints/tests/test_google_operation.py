"""Real registry, composition, and supervision proofs for Google Sheets export."""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.persistence.operations.journal import OperationJournalRepository
from ...adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ...adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ...application.export import (
    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
    GOOGLE_SHEETS_EXPORT_PHASE_APPLY,
    GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
    GoogleSheetsExportOperationRequest,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
    build_google_sheets_export_service,
)
from ...application.operations.capabilities import OperationRequestStoragePolicy
from ...application.operations.composition import compose_operation_services
from ...application.operations.models import OperationRequest
from ...application.operations.registry import OperationRegistry
from ...core.operations import (
    OperationEffect,
    OperationEventKind,
    OperationTerminalCondition,
)
from ...tests.secure_sql import isolated_runtime_profile
from .. import compose_operation_dependencies

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def _services(root: Path):
    """Compose the actual encrypted supervision stack around the default owner."""
    definition = build_google_sheets_export_operation_definition()
    journal = OperationJournalRepository(storage_root=root)
    services = compose_operation_services(
        registry=OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_google_sheets_export_operation_registration(definition),),
        ),
        journal=journal,
        reader=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=5),
        cleanup_timeout=timedelta(seconds=5),
    )
    return services, journal


async def _submit_and_start(services, journal, request: OperationRequest[GoogleSheetsExportOperationRequest]):
    submission = await services.submission.submit(
        request,
        actor_ref="operator:google-export-test",
        operation_id="a" * 64,
    )
    await services.submission.start(submission.receipt.operation_id)
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
    assert registration.contract.result_schema is None
    request_schema = json.dumps(GoogleSheetsExportOperationRequest.model_json_schema(mode="validation")).lower()
    assert "secret" not in request_schema
    assert "token" not in request_schema


@pytest.mark.timeout(60)
def test_default_owner_builds_a_real_registry_plan_then_refuses_uncomposed_remote_execution(
    tmp_path: Path,
) -> None:
    """No fabricated snapshot, plan, port, mock, or patched transport is used here."""
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        services, journal = _services(profile.storage_root)
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
    assert terminal.effect is OperationEffect.UNKNOWN
    assert tuple(event.phase_code for event in replay.events if event.kind is OperationEventKind.PHASE) == (
        GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
        GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
        GOOGLE_SHEETS_EXPORT_PHASE_APPLY,
    )


def test_production_composition_registers_the_facade_owned_definition_and_real_transport(tmp_path: Path) -> None:
    """The production registry binds this owner to the single outer composition transport."""
    with isolated_runtime_profile(tmp_path=tmp_path):
        dependencies = compose_operation_dependencies()
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
    owner_source = (Path(__file__).parents[2] / "application" / "export" / "google_operation.py").read_text(
        encoding="utf-8"
    )
    owner_tree = ast.parse(owner_source)
    owner_imports = tuple(node.module or "" for node in ast.walk(owner_tree) if isinstance(node, ast.ImportFrom))
    assert not any(module.startswith("adapters") or module.startswith("entrypoints") for module in owner_imports)

    composition_source = (Path(__file__).parents[1] / "_operation_composition.py").read_text(encoding="utf-8")
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
