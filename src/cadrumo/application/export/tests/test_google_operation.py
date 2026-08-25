"""Real supervision and boundary proofs for the Google Sheets export operation."""

from __future__ import annotations

import ast
import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ....adapters.outbound.storage import resolve_drive_root_folder_id
from ....adapters.persistence.operations import (
    OperationJournalRepository,
    OperationLeaseFilesystemRepository,
    operation_secure_reference_repository,
)
from ....adapters.persistence.profile import SyncRunRecordRepository
from ....application.operations import (
    OperationEffect,
    OperationRegistry,
    OperationRequest,
    OperationRequestStoragePolicy,
    OperationTerminalCondition,
    compose_operation_services,
)
from ....core.config import load_settings, override_settings
from ....tests.secure_sql import isolated_runtime_profile
from .._google_operation import (
    GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
    GOOGLE_SHEETS_EXPORT_PHASE_PLAN,
    GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT,
    GoogleSheetsExportOperationRequest,
    build_google_sheets_export_operation_definition,
    build_google_sheets_export_operation_registration,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def _configured_drive_root(profile_id: str) -> str:
    """Resolve the Drive root through the real outbound configuration authority."""
    return resolve_drive_root_folder_id(profile=profile_id, settings=load_settings())


def _operation_definition():
    return build_google_sheets_export_operation_definition(drive_root_resolver=_configured_drive_root)


def _services(root: Path, *, profile_objects: object):
    """Compose the real encrypted operation stack around the owner definition."""
    definition = _operation_definition()
    journal = OperationJournalRepository(storage_root=root)
    services = compose_operation_services(
        registry=OperationRegistry(
            definitions=(definition,),
            public_registrations=(build_google_sheets_export_operation_registration(definition),),
        ),
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operation_secure_reference_repository(objects=profile_objects),  # type: ignore[arg-type]
        owner_id="1" * 64,
        lease_token_factory=lambda: "2" * 64,
        clock=lambda: datetime.now(UTC),
        lease_duration=timedelta(minutes=5),
    )
    return services, journal


def test_google_sheets_export_definition_declares_one_safe_credential_free_contract() -> None:
    definition = _operation_definition()
    registration = build_google_sheets_export_operation_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
    request = GoogleSheetsExportOperationRequest(
        profile_id="11111111-1111-4111-8111-111111111111",
        modelo="130",
        filing_year=2025,
        period="1T",
        prefill_relations=True,
        dry_run=True,
    )

    assert GoogleSheetsExportOperationRequest.model_validate_json(request.model_dump_json()) == request
    assert registry.lookup(GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID).capabilities.request_storage is (
        OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    )
    assert registration.contract.request_schema.schema_id == "export.google-sheets.request"
    assert registration.contract.result_schema is None
    request_schema = json.dumps(GoogleSheetsExportOperationRequest.model_json_schema(mode="validation")).lower()
    assert "secret" not in request_schema
    assert "token" not in request_schema


def test_google_sheets_export_plans_with_the_real_registry_before_a_local_root_refusal(tmp_path: Path) -> None:
    """The offline failure reaches real plan construction but never accesses Google.

    An empty real Drive-root configuration is the deterministic preflight
    refusal: the operation has already resolved the registry and constructed
    its workbook plan, yet no credential or Google client can be touched.
    """
    with isolated_runtime_profile(tmp_path=tmp_path) as profile, override_settings(
        cadrumo_google_drive_root_folder_id=""
    ):
        services, journal = _services(profile.storage_root, profile_objects=profile.repository)
        request = OperationRequest(
            definition_id=GOOGLE_SHEETS_EXPORT_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile.bucket_id}",
            payload=GoogleSheetsExportOperationRequest(
                profile_id=profile.bucket_id,
                modelo="130",
                filing_year=2025,
                period="1T",
            ),
        )
        try:
            submission = asyncio.run(
                services.submission.submit(
                    request,
                    actor_ref="operator:google-export-test",
                    operation_id="a" * 64,
                )
            )
            asyncio.run(services.submission.start(submission.receipt.operation_id))
            terminal = asyncio.run(journal.load(submission.receipt.operation_id))
            replay = asyncio.run(journal.read_after(submission.receipt.operation_id, 0, limit=20))

            assert terminal.terminal_condition is OperationTerminalCondition.REFUSED
            assert terminal.effect is OperationEffect.NONE
            assert terminal.terminal_receipt is not None
            assert terminal.terminal_receipt.result_ref is None
            phase_codes = tuple(event.phase_code for event in replay.events if event.phase_code is not None)
            assert phase_codes == (GOOGLE_SHEETS_EXPORT_PHASE_PREFLIGHT, GOOGLE_SHEETS_EXPORT_PHASE_PLAN)
            assert tuple(SyncRunRecordRepository().iter_ids()) == ()
        finally:
            asyncio.run(services.shutdown())


def test_google_export_owner_uses_existing_plan_and_write_authorities_without_cli_imports() -> None:
    """Pin the single owner to existing authorities instead of a frontend clone."""
    source_path = Path(__file__).parents[1] / "_google_operation.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = tuple(node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom))
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }

    assert "cadrumo.entrypoints" not in "\n".join(imported_modules)
    assert {"build_export_plan", "export_modelo_to_sheets", "preview_export_plan"}.issubset(imported_names)
