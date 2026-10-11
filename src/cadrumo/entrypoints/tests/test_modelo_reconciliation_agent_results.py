"""An agent holds the file name of reconciliation evidence and not the directory it was typed in.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted each invocation. An
import reads a file the person named, a pull reads evidence already in the
profile's store, and a listing returns what earlier ones recorded. For an
execution admitted on MCP the released result carries the file name and says
the directory was withheld; the stored record keeps the path as it was typed,
and a person's result is unchanged.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest

from ...adapters.persistence.profile.modelo_reconciliation import ModeloReconciliationPersistence
from ...application.modelo.reconciliation_import_operation import (
    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
    ModeloReconciliationImportProjection,
    ModeloReconciliationImportRequest,
)
from ...application.modelo.reconciliation_list_operation import (
    MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
    ModeloReconciliationListProjection,
    ModeloReconciliationListRequest,
)
from ...application.modelo.reconciliation_pull_operation import (
    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
    ModeloReconciliationPullRequest,
    reconciliation_pull_source_ref,
)
from ...application.modelo.reconciliation_records import ModeloReconciliationEvidenceKind
from ...application.modelo.reconciliation_source_reference import agent_source_reference
from ...application.operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...application.operations.models import OperationIdentity
from ...application.operations.registry import OperationFrontendProjection
from ...application.user_profile.access_contracts import SessionKind
from ...core.config import override_settings
from ...core.hashing import sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..justificante_composition import build_justificante_capture_service
from . import modelo_operation_test_support
from . import test_registered_executor_conformance as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_JUSTIFICANTE_FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
)
_FRONTENDS = pytest.mark.parametrize("frontend", [_MCP, _CLI], ids=["mcp", "cli"])


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        del identity
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


def _directory_of_the_typed_path() -> str:
    """The directory as it appears inside serialized JSON, where a backslash is escaped."""
    return json.dumps(str(_JUSTIFICANTE_FIXTURE.parent))[1:-1]


def test_an_agents_reference_keeps_a_file_name_and_passes_a_stored_handle_through() -> None:
    assert agent_source_reference(str(_JUSTIFICANTE_FIXTURE)) == ("2024-1T.pdf", True)
    assert agent_source_reference("C:\\synthetic\\evidence\\receipt.pdf") == ("receipt.pdf", True)
    assert agent_source_reference("/synthetic/evidence/receipt.pdf") == ("receipt.pdf", True)
    assert agent_source_reference("/synthetic/evidence/") == ("evidence", True)
    assert agent_source_reference("/") == ("", True)
    handle = reconciliation_pull_source_ref(ModeloReconciliationEvidenceKind.JUSTIFICANTE, "a" * 32, None)
    assert agent_source_reference(handle) == (handle, False)


@_FRONTENDS
def test_reconciliation_import_result_withholds_the_directory_from_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """The comparison against the command runs on the typed path; only the released result is sealed."""
    definition_id = MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(frontend),
    ) as (driver, registry, profile_id):
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            request = ModeloReconciliationImportRequest(
                profile_id=profile_id,
                work_unit_id=unit.work_unit_id,
                source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                source_path=str(_JUSTIFICANTE_FIXTURE),
            )

            submitted, observed = asyncio.run(
                driver.run(
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )
            stored = tuple(ModeloReconciliationPersistence().iter_records())[-1]

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert observed.projection.effect is OperationEffect.UPDATED
        released = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloReconciliationImportProjection,
        )

    assert stored.source_ref == str(_JUSTIFICANTE_FIXTURE)
    if frontend is _MCP:
        assert released.source_path == "2024-1T.pdf"
        assert released.source_directory_withheld is True
        assert _directory_of_the_typed_path() not in released.model_dump_json()
    else:
        assert released.source_path == str(_JUSTIFICANTE_FIXTURE)
        assert released.source_directory_withheld is False


@_FRONTENDS
def test_reconciliation_pull_result_names_a_stored_handle_and_no_directory_for_either_frontend(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """A pull reads the profile's store: its source is a handle, which the agent's seal leaves as it is."""
    definition_id = MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(frontend),
    ) as (driver, registry, profile_id):
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            pdf = _JUSTIFICANTE_FIXTURE.read_bytes()
            snapshot = build_justificante_capture_service(str(profile_id)).capture(
                modelo=str(unit.modelo),
                filing_year=unit.filing_year,
                period=unit.period,
                expediente_id="202413000000001Z",
                csv="ABCD1234EFGH",
                pdf_bytes=pdf,
                pdf_sha256=sha256_hex(pdf),
                captured_at=datetime(2026, 9, 29, tzinfo=UTC),
            )
            request = ModeloReconciliationPullRequest(
                profile_id=profile_id, work_unit_id=unit.work_unit_id, snapshot_id=snapshot.snapshot_id
            )

            submitted, observed = asyncio.run(
                driver.run(
                    definition_id=definition_id,
                    subject_ref=profile_operation_subject(str(profile_id)),
                    payload=request,
                )
            )

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        released = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=definition_id,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloReconciliationImportProjection,
        )

    handle = reconciliation_pull_source_ref(ModeloReconciliationEvidenceKind.JUSTIFICANTE, snapshot.snapshot_id, None)
    assert released.source_path == handle
    assert released.source_directory_withheld is False


@_FRONTENDS
def test_reconciliation_list_seals_each_recorded_path_for_an_agent(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """A listing of an earlier import's typed path and an earlier pull's handle."""
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(frontend),
    ) as (driver, registry, profile_id):
        subject_ref = profile_operation_subject(str(profile_id))
        with override_settings(cadrumo_active_profile=str(profile_id)):
            unit = modelo_operation_test_support.seeded_modelo_work_unit(profile_id, operation=operation)
            pdf = _JUSTIFICANTE_FIXTURE.read_bytes()
            snapshot = build_justificante_capture_service(str(profile_id)).capture(
                modelo=str(unit.modelo),
                filing_year=unit.filing_year,
                period=unit.period,
                expediente_id="202413000000001Z",
                csv="ABCD1234EFGH",
                pdf_bytes=pdf,
                pdf_sha256=sha256_hex(pdf),
                captured_at=datetime(2026, 9, 29, tzinfo=UTC),
            )
            for definition_id, payload in (
                (
                    MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID,
                    ModeloReconciliationImportRequest(
                        profile_id=profile_id,
                        work_unit_id=unit.work_unit_id,
                        source_kind=ModeloReconciliationEvidenceKind.JUSTIFICANTE,
                        source_path=str(_JUSTIFICANTE_FIXTURE),
                    ),
                ),
                (
                    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                    ModeloReconciliationPullRequest(
                        profile_id=profile_id, work_unit_id=unit.work_unit_id, snapshot_id=snapshot.snapshot_id
                    ),
                ),
            ):
                _recorded, recorded_observation = asyncio.run(
                    driver.run(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
                )
                assert recorded_observation.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED

            submitted, observed = asyncio.run(
                driver.run(
                    definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=ModeloReconciliationListRequest(profile_id=profile_id),
                )
            )
            stored = {record.source_ref for record in ModeloReconciliationPersistence().iter_records()}

        assert observed.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
        listing = conformance._resolve_result_projection(
            driver,
            registry,
            definition_id=MODELO_RECONCILIATION_LIST_OPERATION_DEFINITION_ID,
            operation_id=submitted.receipt.operation_id,
            terminal_revision=observed.projection.revision,
            projection_type=ModeloReconciliationListProjection,
        )

    handle = reconciliation_pull_source_ref(ModeloReconciliationEvidenceKind.JUSTIFICANTE, snapshot.snapshot_id, None)
    assert stored == {str(_JUSTIFICANTE_FIXTURE), handle}
    assert listing.reconciliation_count == 2
    shown = {row.source_path: row.source_directory_withheld for row in listing.reconciliations}
    if frontend is _MCP:
        assert shown == {"2024-1T.pdf": True, handle: False}
        assert _directory_of_the_typed_path() not in listing.model_dump_json()
    else:
        assert shown == {str(_JUSTIFICANTE_FIXTURE): False, handle: False}
