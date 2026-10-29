"""A confirm whose re-read needs the local AI settles with the agent service's verdict in its detail.

Confirming a document reads it again through the same composed readers as the
extraction. The registered confirm runs through the real registry, supervisor,
journal and encrypted operand store, with its production composition, against
a stored image. Its model runs reach a recording stand-in for the agent
service through an execution authority, as the runtime host's authority
relays them, and the service reports the vision selection's model is not
installed. The refusal is read back the way a frontend in another process
reads it: as the operation's recorded error detail, which must carry the
verdict naming the missing model, with no run sent to the service.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from ...adapters.outbound.llm.preconditions import LLMPreconditionCondition
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import operation_repositories
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.evidence_errors import PurchaseInvoiceEvidenceReaderError
from ...application.ledger.invoice_evidence_confirm_operation import (
    LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
    LedgerEvidenceConfirmRequest,
    build_ledger_evidence_confirm_definition,
    build_ledger_evidence_confirm_registration,
)
from ...application.operations.error_detail import (
    OperationErrorDetailKind,
    OperationErrorDetailV1,
    operation_error_detail_schema,
)
from ...application.operations.frontend_requests import (
    OperationResultProjectionRequestV1,
    OperationResultProjectionSuccessV1,
)
from ...application.operations.models import OperationRequest
from ...application.operations.projection_services import OperationResultProjectionService
from ...application.operations.registry import OperationRegistry
from ...application.operations.supervisor import OperationSupervisor
from ...core.errors.error_codes import get_registered_error_code
from ...core.model_roles import ModelRole
from ...core.operations import OperationTerminalCondition, profile_operation_subject
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...domain.iva.schema import InvoiceKind
from ...tests.llm_vision_evidence_support import png_image
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports
from .dependency_operation_gating_support import RecordingRunsAuthority, agent_refusing

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("6c1d3e5f-7a9b-4c2d-8e4f-5a6b7c8d9e0f")
_REGISTERED = get_registered_error_code(PurchaseInvoiceEvidenceReaderError)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _stored_image(profile: TestRuntimeProfile) -> tuple[str, str]:
    data = png_image()
    store = AttachmentStore(objects=profile.repository)
    attachment_id = store.put_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=AttachmentKind.RECEIPT_IMAGE,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="confirm-reader-refusal-evidence",
            sha256=digest,
            mime_type="image/png",
            bytes_size=len(data),
            captured_at=datetime(2026, 10, 24, 9, 0, tzinfo=UTC),
            bucket_id=str(_PROFILE),
            captured_by="operator",
            source_command="aeat app ledger attach",
        )
    )
    return attachment_id, digest


def test_a_confirm_whose_re_read_needs_the_vision_model_settles(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id, digest = _stored_image(profile)
    definition = build_ledger_evidence_confirm_definition(build_invoice_evidence_operation_ports)
    registration = build_ledger_evidence_confirm_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))

    async def settle(
        supervisor: OperationSupervisor, service: OperationResultProjectionService
    ) -> tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1]:
        operation_id = await supervisor.submit(
            OperationRequest[BaseModel](
                definition_id=LEDGER_EVIDENCE_CONFIRM_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
                payload=LedgerEvidenceConfirmRequest(
                    profile_id=_PROFILE,
                    attachment_id=attachment_id,
                    expected_source_sha256=digest,
                    expected_draft_review_sha256="e" * 64,
                    kind=InvoiceKind.RECEIVED,
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
                result_schema=operation_error_detail_schema(),
            ),
            OperationErrorDetailV1,
        )
        assert isinstance(resolved, OperationResultProjectionSuccessV1), resolved
        detail = resolved.projection
        assert isinstance(detail, OperationErrorDetailV1)
        return receipt.condition, receipt.refusal_ref, detail

    with agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as agent:
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
        condition, refusal_ref, detail = asyncio.run(settle(supervisor, service))

    assert condition is OperationTerminalCondition.REFUSED
    assert refusal_ref == _REGISTERED.code
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _REGISTERED.code
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the service's verdict"
    assert verdict.failed_condition_id == LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED.value
    assert verdict.evidence[0].values["role"] == ModelRole.VISION_TRANSCRIPTION.value
    assert verdict.action is None
    assert agent.lookups == [ModelRole.VISION_TRANSCRIPTION]
    assert agent.runs == [], "a run was sent for a role whose model is not installed"
