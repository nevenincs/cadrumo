"""A batch whose reader is missing settles with the agent service's verdict in its result.

Evidence ingestion does not refuse the run when the local AI is not ready.
The first document that needs the role is attempted, and the service's
refusal is that document's own: it names the local AI setup and closes the
role for the rest of the run, so every later document that needs it pauses
unread. The settled result carries the verdict, so it reaches a frontend in
another process through the result projection rather than through an error
detail. The registered batch runs through the real registry, supervisor,
journal and encrypted operand store, with its production composition, against
real text-layer PDFs. Its model runs reach a recording stand-in for the agent
service through an execution authority, as the runtime host's authority
relays them. No run may reach the service.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import operation_repositories
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.evidence_ingestion_contracts import (
    LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
    LedgerEvidenceBatchProjection,
    LedgerEvidenceBatchRequest,
)
from ...application.ledger.evidence_ingestion_operation import (
    build_ledger_evidence_ingestion_definitions,
    build_ledger_evidence_ingestion_registrations,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ...core.config import override_settings
from ...core.model_roles import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva.schema import InvoiceKind
from ...tests.pdf_fixtures import text_pdf_bytes
from ..ledger_evidence_ingestion_operation_composition import build_ledger_evidence_ingestion_operation_ports
from .dependency_operation_gating_support import RecordingRunsAuthority, agent_refusing

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("9f4a6b8c-0d1e-4f2a-9b3c-8d9e0f1a2b3c")

#: Figures with no label the rules read, so each document needs the text model.
_NO_LABELS = ("B1234567X B17283946 766,30",)
_OTHER_NO_LABELS = ("B7654321X B17283946 412,90",)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def test_a_batch_paused_for_its_missing_text_model_settles_with_the_local_ai_setup_in_its_result(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    folder = tmp_path / "documents"
    folder.mkdir()
    first = folder / "first-unlabelled.pdf"
    first.write_bytes(text_pdf_bytes(_NO_LABELS))
    second = folder / "second-unlabelled.pdf"
    second.write_bytes(text_pdf_bytes(_OTHER_NO_LABELS))
    definitions = build_ledger_evidence_ingestion_definitions(build_ledger_evidence_ingestion_operation_ports)
    registrations = build_ledger_evidence_ingestion_registrations(definitions)
    (registration,) = registrations
    registry = OperationRegistry(definitions=definitions, public_registrations=registrations)
    result_schema = registration.contract.result_schema
    assert result_schema is not None

    async def settle(
        supervisor: OperationSupervisor, service: OperationResultProjectionService
    ) -> tuple[OperationTerminalCondition, OperationEffect, LedgerEvidenceBatchProjection]:
        operation_id = await supervisor.submit(
            OperationRequest[BaseModel](
                definition_id=LEDGER_EVIDENCE_BATCH_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
                payload=LedgerEvidenceBatchRequest(
                    profile_id=_PROFILE,
                    sources=(str(first), str(second)),
                    source_directory=str(folder),
                    direction=InvoiceKind.RECEIVED,
                ),
            ),
            operation_id="4" * 64,
        )
        terminal = await run_to_settlement(supervisor, operation_id)
        receipt = terminal.terminal_receipt
        assert receipt is not None
        resolved = await service.resolve(
            OperationResultProjectionRequestV1(
                operation_id=operation_id,
                terminal_revision=terminal.revision,
                definition_contract_digest=registration.contract.definition_contract_digest,
                result_schema=result_schema,
            ),
            LedgerEvidenceBatchProjection,
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
        projection = resolved.projection
        assert isinstance(projection, LedgerEvidenceBatchProjection)
        return receipt.condition, receipt.effect, projection

    # Admission control is configured for a host whose headroom cannot be
    # measured, the documented operator setting, so the only cause to stop is
    # the reader itself.
    with (
        agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as agent,
        override_settings(cadrumo_llm_contention_check_override=True),
    ):
        journal, leases, operands = operation_repositories(
            storage_root=tmp_path / "durable-state", profile_objects=profile.repository
        )
        supervisor = OperationSupervisor(
            authority_operation=operation,
            registry=registry,
            journal=journal,
            event_stream=journal,
            leases=leases,
            operands=operands,
            owner_id="1" * 64,
            lease_token_factory=lambda: "2" * 64,
            clock=lambda: datetime.now(UTC),
            lease_duration=timedelta(minutes=5),
            execution_timeout=timedelta(minutes=2),
            cleanup_timeout=timedelta(minutes=1),
            response_token_factory=lambda: "3" * 64,
            execution_authority=RecordingRunsAuthority(agent),
        )
        service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
        condition, effect, projection = asyncio.run(settle(supervisor, service))

    assert condition is OperationTerminalCondition.SUCCEEDED
    # The first document's evidence was stored before its read was refused and the second
    # was never touched, so the run wrote something and left work undone.
    assert effect is OperationEffect.PARTIAL
    run = projection.run.to_run()
    attempted, paused = run.items
    assert attempted.source_name == first.name
    assert attempted.status == "refused"
    refused = attempted.refusal_verdict
    assert refused is not None
    assert paused.source_name == second.name
    assert paused.status == "paused"
    assert paused.refusal_verdict is None
    pause = run.inference_pause
    assert pause is not None, "the settled result lost the service's verdict"
    for verdict in (refused, pause.precondition_verdict):
        assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
        assert verdict.evidence[0].values["role"] == ModelRole.TEXT_EXTRACTION.value
        assert verdict.action is not None
        assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    # The closed role is not asked again for the second document.
    assert agent.lookups == [ModelRole.TEXT_EXTRACTION]
    assert agent.runs == [], "a run was sent for a role whose model is not installed"
