"""A batch whose reader is missing settles with the reader probe's verdict in its result.

Evidence ingestion does not refuse when the local AI is not ready: it pauses
the documents that need a model and reports why in the settled result, so the
verdict reaches a frontend in another process through the result projection
rather than through an error detail. The registered batch runs through the
real registry, supervisor, journal and encrypted operand store, with its
production composition, against a real text-layer PDF and a real loopback
runtime that answers its model inventory. No read may be sent to the runtime.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http import HTTPStatus
from pathlib import Path
from typing import ClassVar, override
from uuid import UUID

import pytest
from pydantic import BaseModel

from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import _repositories
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
from ...application.local_reader import configured_role_model
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
from ...core.model_catalogue import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva.schema import InvoiceKind
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...tests.pdf_fixtures import text_pdf_bytes
from ..ledger_evidence_ingestion_operation_composition import build_ledger_evidence_ingestion_operation_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("9f4a6b8c-0d1e-4f2a-9b3c-8d9e0f1a2b3c")

#: Figures with no label the rules read, so the document needs the text model.
_NO_LABELS = ("B1234567X B17283946 766,30",)


class _InventoryRuntime(SilentLoopbackHandler):
    """A real runtime endpoint that answers its inventory and records every read it is sent."""

    installed: ClassVar[tuple[str, ...]] = ()
    reads: ClassVar[list[str]] = []

    @override
    def do_GET(self) -> None:
        names = self.installed if self.path == "/api/tags" else ()
        write_json_response(self, {"models": [{"name": name, "size": 1} for name in names]}, status=HTTPStatus.OK)

    @override
    def do_POST(self) -> None:
        self.reads.append(self.path)
        self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


@contextmanager
def _runtime_holding_only_the_vision_model() -> Generator[None]:
    """Serve a runtime that holds the vision model but not the text model a text-layer PDF needs.

    Admission control is configured for a host whose headroom cannot be
    measured, the documented operator setting, so the lane's only cause to
    pause is the reader itself.
    """
    _InventoryRuntime.reads = []
    vision = configured_role_model(ModelRole.VISION_TRANSCRIPTION)
    _InventoryRuntime.installed = () if vision is None else (vision,)
    with (
        serving_loopback(_InventoryRuntime, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url, cadrumo_llm_contention_check_override=True),
    ):
        yield


def test_a_batch_paused_for_its_missing_text_model_settles_with_the_local_ai_setup_in_its_result(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    folder = tmp_path / "documents"
    folder.mkdir()
    document = folder / "unlabelled.pdf"
    document.write_bytes(text_pdf_bytes(_NO_LABELS))
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
                    sources=(str(document),),
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

    with _runtime_holding_only_the_vision_model():
        journal, leases, operands = _repositories(
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
        )
        service = OperationResultProjectionService(reader=journal, registry=registry, operands=operands)
        condition, effect, projection = asyncio.run(settle(supervisor, service))

    assert condition is OperationTerminalCondition.SUCCEEDED
    assert effect is OperationEffect.NONE, "a paused document must not be stored"
    (item,) = projection.run.items
    assert item.status == "paused"
    pause = projection.run.inference_pause
    assert pause is not None, "the settled result lost the reader probe's verdict"
    verdict = pause.precondition_verdict.to_verdict()
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == ModelRole.TEXT_EXTRACTION.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert _InventoryRuntime.reads == [], "a read was sent before the reader was checked"
