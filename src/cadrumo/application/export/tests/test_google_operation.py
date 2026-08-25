"""Real supervision and hex-boundary proofs for the Google Sheets export operation."""

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

from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.storage import SecureObjectRepository
from ....application.operations import (
    OperationEffect,
    OperationEventKind,
    OperationRegistry,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationTerminalCondition,
    compose_operation_services,
)
from ....application.storage.calc_sheets import SheetExportPlan
from ....domain.calculations.registry import RegistrySnapshot
from ....tests.secure_sql import isolated_runtime_profile
from .._google_operation import (
    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
    GOOGLE_SHEETS_EXPORT_PHASE_APPLY,
    GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
    GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW,
    GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT,
    GoogleSheetsExportOperationRequest,
    GoogleSheetsExportRemoteResult,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _snapshot_resolver(modelo: str, _period: object) -> RegistrySnapshot:
    """Supply only the stable registry facts the owner must retain."""
    return cast(
        RegistrySnapshot,
        SimpleNamespace(
            modelo=SimpleNamespace(id=modelo),
            revision=SimpleNamespace(id="r2025"),
        ),
    )


def _plan_builder(_snapshot: RegistrySnapshot, **_kwargs: object) -> SheetExportPlan:
    """Keep the operation test on its owner boundary, not the engine's tests."""
    return cast(
        SheetExportPlan,
        SimpleNamespace(
            metadata=SimpleNamespace(engine_version="calc-sheets-test", registry_sha="a" * 64),
            value_cells=(),
            formula_cells=(),
            protected_ranges=(),
        ),
    )


def _operation_definition(*, export_port):
    return build_google_sheets_export_operation_definition(
        export_port=export_port,
        snapshot_resolver=_snapshot_resolver,
        plan_builder=_plan_builder,
    )


def _services(root: Path, *, profile_objects: SecureObjectRepository, export_port):
    """Compose the real encrypted operation stack around the application owner."""
    definition = _operation_definition(export_port=export_port)
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
        operands=operation_secure_reference_repository(objects=profile_objects),
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
        execution_timeout=timedelta(seconds=5),
        cleanup_timeout=timedelta(seconds=5),
    )
    return services, journal


async def _submit_and_start(services, journal, request: OperationRequest[GoogleSheetsExportOperationRequest], operation_id: str):
    submission = await services.submission.submit(
        request,
        actor_ref="operator:google-export-test",
        operation_id=operation_id,
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


@pytest.mark.parametrize("dry_run", [False, True])
def test_google_sheets_export_is_supervised_through_an_injected_port(
    tmp_path: Path,
    dry_run: bool,
) -> None:
    """The owner records the correct branch without importing or invoking Google."""
    calls: list[tuple[str, bool]] = []

    def export_port(profile_id: str, _plan: SheetExportPlan, requested_dry_run: bool) -> GoogleSheetsExportRemoteResult:
        calls.append((profile_id, requested_dry_run))
        return GoogleSheetsExportRemoteResult(
            dry_run=requested_dry_run,
            spreadsheet_exists=True if requested_dry_run else None,
            folder_id="folder-1",
            spreadsheet_id="sheet-1",
            spreadsheet_url="https://example.test/sheet-1",
            value_cells_written=3,
            formula_cells_written=2,
            protected_ranges_written=1,
            tab_count=7,
            ranges_to_clear=("Datos!A1",) if requested_dry_run else (),
            value_cells_changed=3 if requested_dry_run else None,
            value_cells_unchanged=0 if requested_dry_run else None,
            formula_cells_to_write=2 if requested_dry_run else None,
        )

    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        services, journal = _services(profile.storage_root, profile_objects=profile.repository, export_port=export_port)
        request = OperationRequest(
            definition_id=GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile.bucket_id}",
            payload=GoogleSheetsExportOperationRequest(
                profile_id=UUID(profile.bucket_id),
                modelo="130",
                filing_year=2025,
                period="1T",
                dry_run=dry_run,
            ),
        )
        try:
            terminal, replay = asyncio.run(_submit_and_start(services, journal, request, "a" * 64))
        finally:
            asyncio.run(services.shutdown())

    assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
    assert terminal.effect is (OperationEffect.NONE if dry_run else OperationEffect.UPDATED)
    assert terminal.terminal_receipt is not None
    assert terminal.terminal_receipt.result_ref is not None
    assert calls == [(profile.bucket_id, dry_run)]
    assert tuple(
        event.phase_code
        for event in replay.events
        if event.kind is OperationEventKind.PHASE
    ) == (
        GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
        GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
        GOOGLE_SHEETS_EXPORT_PHASE_PREVIEW if dry_run else GOOGLE_SHEETS_EXPORT_PHASE_APPLY,
        GOOGLE_SHEETS_EXPORT_PHASE_SETTLEMENT,
    )


def test_google_export_owner_has_no_concrete_adapter_or_entrypoint_dependency() -> None:
    """Pin the canonical owner to application/core contracts and its injected port."""
    source_path = Path(__file__).parents[1] / "_google_operation.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert not any(module.startswith("cadrumo.adapters") for module in imported_modules)
    assert not any(module.startswith("cadrumo.entrypoints") for module in imported_modules)
    assert {"build_export_plan", "resolve_relations_from_local_store"}.issubset(imported_names)
