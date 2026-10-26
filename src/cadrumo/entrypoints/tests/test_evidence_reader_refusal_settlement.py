"""A refused evidence read settles with the agent service's typed verdict, so every frontend can act on it.

The registered extraction operation runs through the real registry,
supervisor, journal and encrypted operand store, with its production
composition, against a stored document. Its model runs reach a recording
stand-in for the agent service through an execution authority, as the runtime
host's authority relays them. The refusal is then read back the way a
frontend in another process reads it: as the operation's recorded error
detail. A selected model that is not installed names the local AI setup; a
role with no selection names the role and says it needs one; an off-host lane
without the person's consent refuses. In every case no run reaches the service.
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

from ...adapters.outbound.llm.errors import LLMConsentError
from ...adapters.outbound.llm.preconditions import LLMPreconditionCondition
from ...adapters.outbound.llm.tests.model_run_support import DEFAULT_LANE, RecordingModelRuns
from ...adapters.persistence.operations.tests.supervision_support import run_to_settlement
from ...adapters.persistence.operations.tests.supervisor_test_support import operation_repositories
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.evidence_errors import (
    EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY,
    EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY,
    PurchaseInvoiceEvidenceReaderError,
)
from ...application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractRequest,
    build_ledger_evidence_extract_definition,
    build_ledger_evidence_extract_registration,
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
from ...application.provisioning_contracts import LOCAL_AI_PROVISION_ACTION_ID, ProvisioningPreconditionCondition
from ...core.errors.error_codes import get_registered_error_code
from ...core.model_roles import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...tests.llm_vision_evidence_support import png_image
from ...tests.pdf_fixtures import text_pdf_bytes
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports
from .dependency_operation_gating_support import RecordingRunsAuthority, agent_refusing

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("7d2e4f6a-8b1c-4d3e-9f5a-6b7c8d9e0f1a")
_REGISTERED = get_registered_error_code(PurchaseInvoiceEvidenceReaderError)

#: Figures with no label the rules read, so the text model is the whole read.
_NO_LABELS = ("B1234567X B17283946 766,30",)


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=str(_PROFILE)) as runtime_profile:
        yield runtime_profile


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _stored(profile: TestRuntimeProfile, data: bytes, *, kind: AttachmentKind, mime_type: str) -> str:
    store = AttachmentStore(objects=profile.repository)
    attachment_id = store.put_bytes(data)
    store.write_manifest(
        Attachment(
            attachment_id=attachment_id,
            kind=kind,
            source=AttachmentSource.LOCAL_FILE,
            source_reference="reader-refusal-evidence",
            sha256=hashlib.sha256(data).hexdigest(),
            mime_type=mime_type,
            bytes_size=len(data),
            captured_at=datetime(2026, 10, 24, 9, 0, tzinfo=UTC),
            bucket_id=str(_PROFILE),
            captured_by="operator",
            source_command="aeat app ledger attach",
        )
    )
    return attachment_id


def _settle_and_read_detail(
    tmp_path: Path,
    profile: TestRuntimeProfile,
    operation: PinnedAuthorityOperation,
    attachment_id: str,
    service: RecordingModelRuns,
) -> tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1]:
    definition = build_ledger_evidence_extract_definition(build_invoice_evidence_operation_ports)
    registration = build_ledger_evidence_extract_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
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
        execution_authority=RecordingRunsAuthority(service),
    )

    async def settle() -> tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1]:
        operation_id = await supervisor.submit(
            OperationRequest[BaseModel](
                definition_id=LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
                payload=LedgerEvidenceExtractRequest(profile_id=_PROFILE, attachment_id=attachment_id),
            ),
            operation_id="4" * 64,
        )
        terminal = await run_to_settlement(supervisor, operation_id)
        receipt = terminal.terminal_receipt
        assert receipt is not None
        assert receipt.effect is OperationEffect.NONE
        resolved = await OperationResultProjectionService(reader=journal, registry=registry, operands=operands).resolve(
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

    return asyncio.run(settle())


def _assert_refused_by_the_reader(
    settled: tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1], message_key: str
) -> OperationErrorDetailV1:
    condition, refusal_ref, detail = settled
    assert condition is OperationTerminalCondition.REFUSED
    assert refusal_ref == _REGISTERED.code
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _REGISTERED.code
    assert detail.message_key == message_key
    return detail


def test_a_text_read_refused_for_its_missing_model_settles_with_the_local_ai_setup(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id = _stored(
        profile, text_pdf_bytes(_NO_LABELS), kind=AttachmentKind.INVOICE_PDF, mime_type="application/pdf"
    )
    with agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as service:
        settled = _settle_and_read_detail(tmp_path, profile, operation, attachment_id, service)

    detail = _assert_refused_by_the_reader(settled, EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY)
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the service's verdict"
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == ModelRole.TEXT_EXTRACTION.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == [], "a run was sent for a role whose model is not installed"


def test_an_image_read_refused_for_its_missing_vision_model_settles_with_the_local_ai_setup(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id = _stored(profile, png_image(), kind=AttachmentKind.RECEIPT_IMAGE, mime_type="image/png")
    with agent_refusing(ModelRunRefusalCode.MODEL_NOT_INSTALLED) as service:
        settled = _settle_and_read_detail(tmp_path, profile, operation, attachment_id, service)

    detail = _assert_refused_by_the_reader(settled, EVIDENCE_LOCAL_AI_NOT_READY_LOCALE_KEY)
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the service's verdict"
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == ModelRole.VISION_TRANSCRIPTION.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert service.lookups == [ModelRole.VISION_TRANSCRIPTION]
    assert service.runs == [], "a run was sent for a role whose model is not installed"


def test_a_text_read_with_no_selection_settles_naming_the_role_that_needs_one(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id = _stored(
        profile, text_pdf_bytes(_NO_LABELS), kind=AttachmentKind.INVOICE_PDF, mime_type="application/pdf"
    )
    with agent_refusing(ModelRunRefusalCode.NO_SELECTION) as service:
        settled = _settle_and_read_detail(tmp_path, profile, operation, attachment_id, service)

    # No setup supplies a selection, so the refusal offers none.
    detail = _assert_refused_by_the_reader(settled, EVIDENCE_READER_UNAVAILABLE_LOCALE_KEY)
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the service's verdict"
    assert verdict.failed_condition_id == LLMPreconditionCondition.AGENT_MODEL_RUN_COMPLETED.value
    facts = verdict.evidence[0].values
    assert facts["model_run_refusal"] == ModelRunRefusalCode.NO_SELECTION.value
    assert facts["role"] == ModelRole.TEXT_EXTRACTION.value
    assert facts["role_selection_required"] is True
    assert verdict.action is None
    assert service.runs == []


def test_a_read_on_an_off_host_lane_without_consent_refuses_and_sends_nothing(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    """The role's lane reads off this computer and the request carries no consent, so the document stays here."""
    attachment_id = _stored(
        profile, text_pdf_bytes(_NO_LABELS), kind=AttachmentKind.INVOICE_PDF, mime_type="application/pdf"
    )
    assert DEFAULT_LANE.reads_off_host
    with agent_refusing(None, lane=DEFAULT_LANE) as service:
        condition, refusal_ref, detail = _settle_and_read_detail(tmp_path, profile, operation, attachment_id, service)

    assert condition is OperationTerminalCondition.REFUSED
    assert refusal_ref == detail.error_code == get_registered_error_code(LLMConsentError).code
    assert service.lookups == [ModelRole.TEXT_EXTRACTION]
    assert service.runs == [], "the document was sent off this computer without consent"
