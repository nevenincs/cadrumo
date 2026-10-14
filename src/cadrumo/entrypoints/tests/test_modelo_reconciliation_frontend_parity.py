"""A reconciliation result names its evidence the same way whichever frontend submitted it.

The production registry and the real executors run over a stored profile with
a session host that answers for the frontend that admitted each invocation. An
import reads a file the person named, a pull reads evidence already in the
profile's store, and a listing returns what earlier ones recorded. Each
released result carries the reference exactly as the stored record keeps it.
"""

from __future__ import annotations

import asyncio
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
from . import registered_executor_case_support as conformance

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_JUSTIFICANTE_FIXTURE = (
    Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "justificantes" / "130" / "2024-1T.pdf"
)


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        del identity
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


@pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection))
def test_import_pull_and_list_release_the_recorded_evidence_reference_on_every_frontend(
    tmp_path: Path,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
) -> None:
    """The typed path of an import and the stored handle of a pull reach the result as they were recorded."""
    typed_path = str(_JUSTIFICANTE_FIXTURE)
    with conformance._runtime(
        tmp_path / "runtime",
        cleanup=conformance._CloseWitness(),
        execution_caller_reader=_session_host(frontend),
    ) as (driver, registry, profile_id):
        subject_ref = profile_operation_subject(str(profile_id))
        released: dict[str, ModeloReconciliationImportProjection] = {}
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
                        source_path=typed_path,
                    ),
                ),
                (
                    MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID,
                    ModeloReconciliationPullRequest(
                        profile_id=profile_id, work_unit_id=unit.work_unit_id, snapshot_id=snapshot.snapshot_id
                    ),
                ),
            ):
                recorded, recorded_observation = asyncio.run(
                    driver.run(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
                )
                assert recorded_observation.projection.terminal_condition is OperationTerminalCondition.SUCCEEDED
                assert recorded_observation.projection.effect is OperationEffect.UPDATED
                released[definition_id] = conformance._resolve_result_projection(
                    driver,
                    registry,
                    definition_id=definition_id,
                    operation_id=recorded.receipt.operation_id,
                    terminal_revision=recorded_observation.projection.revision,
                    projection_type=ModeloReconciliationImportProjection,
                )

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
    assert stored == {typed_path, handle}
    assert released[MODELO_RECONCILIATION_IMPORT_OPERATION_DEFINITION_ID].source_path == typed_path
    assert released[MODELO_RECONCILIATION_PULL_OPERATION_DEFINITION_ID].source_path == handle
    assert listing.reconciliation_count == 2
    assert {row.source_path for row in listing.reconciliations} == {typed_path, handle}
