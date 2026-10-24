"""A refused evidence read settles with the reader probe's verdict, so every frontend can offer setup.

The registered extraction operation runs through the real registry,
supervisor, journal and encrypted operand store, with its production
composition, against a stored document and a real loopback runtime that
answers its model inventory. The refusal is then read back the way a frontend
in another process reads it: as the operation's recorded error detail. That
detail must carry the verdict naming the local AI setup, and no read may be
sent to the runtime first.
"""

from __future__ import annotations

import asyncio
import hashlib
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
from ...adapters.persistence.storage.attachment import AttachmentStore
from ...adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from ...application.ledger.evidence_errors import EVIDENCE_LOCAL_AI_NOT_READY_KEY, PurchaseInvoiceEvidenceReaderError
from ...application.ledger.invoice_evidence_extract_operation import (
    LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
    LedgerEvidenceExtractRequest,
    build_ledger_evidence_extract_definition,
    build_ledger_evidence_extract_registration,
)
from ...application.local_reader import configured_role_model
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
from ...core.config import override_settings
from ...core.errors.error_codes import get_registered_error_code
from ...core.model_catalogue import ModelRole
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.models import Attachment
from ...domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...tests.llm_vision_evidence_support import png_image
from ...tests.loopback_llm import SilentLoopbackHandler, serving_loopback, write_json_response
from ...tests.pdf_fixtures import text_pdf_bytes
from ..invoice_evidence_operation_composition import build_invoice_evidence_operation_ports

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE = UUID("7d2e4f6a-8b1c-4d3e-9f5a-6b7c8d9e0f1a")
_REGISTERED = get_registered_error_code(PurchaseInvoiceEvidenceReaderError)

#: Figures with no label the rules read, so the text model is the whole read.
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
def _runtime_holding(role: ModelRole) -> Generator[None]:
    """Serve a runtime holding only the configured model of ``role``."""
    _InventoryRuntime.reads = []
    model = configured_role_model(role)
    _InventoryRuntime.installed = () if model is None else (model,)
    with (
        serving_loopback(_InventoryRuntime, path="/api/chat") as chat_url,
        override_settings(cadrumo_llm_ollama_chat_url=chat_url),
    ):
        yield


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
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation, attachment_id: str
) -> tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1]:
    definition = build_ledger_evidence_extract_definition(build_invoice_evidence_operation_ports)
    registration = build_ledger_evidence_extract_registration(definition)
    registry = OperationRegistry(definitions=(definition,), public_registrations=(registration,))
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


def _assert_names_the_local_ai_setup(
    settled: tuple[OperationTerminalCondition, str | None, OperationErrorDetailV1], role: ModelRole
) -> None:
    condition, refusal_ref, detail = settled
    assert condition is OperationTerminalCondition.REFUSED
    assert refusal_ref == _REGISTERED.code
    assert detail.kind is OperationErrorDetailKind.REGISTERED_ERROR
    assert detail.error_code == _REGISTERED.code
    assert detail.message_key == EVIDENCE_LOCAL_AI_NOT_READY_KEY
    verdict = detail.precondition_verdict()
    assert verdict is not None, "the settled refusal lost the reader probe's verdict"
    assert verdict.failed_condition_id == ProvisioningPreconditionCondition.ROLE_MODEL_INSTALLED.value
    assert verdict.evidence[0].values["role"] == role.value
    assert verdict.action is not None
    assert verdict.action.action_id == LOCAL_AI_PROVISION_ACTION_ID
    assert _InventoryRuntime.reads == [], "a read was sent before the reader was checked"


def test_a_text_read_refused_for_its_missing_model_settles_with_the_local_ai_setup(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id = _stored(
        profile, text_pdf_bytes(_NO_LABELS), kind=AttachmentKind.INVOICE_PDF, mime_type="application/pdf"
    )
    with _runtime_holding(ModelRole.VISION_TRANSCRIPTION):
        settled = _settle_and_read_detail(tmp_path, profile, operation, attachment_id)

    _assert_names_the_local_ai_setup(settled, ModelRole.TEXT_EXTRACTION)


def test_an_image_read_refused_for_its_missing_vision_model_settles_with_the_local_ai_setup(
    tmp_path: Path, profile: TestRuntimeProfile, operation: PinnedAuthorityOperation
) -> None:
    attachment_id = _stored(profile, png_image(), kind=AttachmentKind.RECEIPT_IMAGE, mime_type="image/png")
    with _runtime_holding(ModelRole.TEXT_EXTRACTION):
        settled = _settle_and_read_detail(tmp_path, profile, operation, attachment_id)

    _assert_names_the_local_ai_setup(settled, ModelRole.VISION_TRANSCRIPTION)
