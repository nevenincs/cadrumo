"""An agent may have a stored document read on this machine, and holds no text from it.

The registered resolver refuses an MCP session the read that sends a document
to a hosted model. The real executor refuses an agent's read while the on-host
reader's endpoint names another machine, and seals for an agent the reading's
summary in place of the draft. A person's read is unchanged on both counts.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....core.config import Settings
from ....core.config_support import LLMProvider
from ....core.field_grounding import FieldGroundingOutcome
from ....core.field_origin import FieldOrigin
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.access_resolution import OperationAccessContext, resolve_operation_access
from ...operations.execution_actor import OperationExecutionCaller, OperationExecutionCallerReader
from ...operations.mcp_admission import McpRuling, mcp_admission_decision
from ...operations.models import OperationIdentity, OperationRequest
from ...operations.owner import OperationExecutorContext
from ...operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationRegistry,
)
from ...user_profile.access_contracts import AccessAction, AccessDenialCode, Availability, SessionKind
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import invoice_evidence_extract_operation as extract_operation
from .. import invoice_evidence_operation as operation_ports
from ..invoice_confirmation import invoice_draft_review_sha256
from ..invoice_draft_extraction_ports import EvidenceConsentProof, InvoiceDraftExtractionPorts
from ..invoice_draft_records import FieldProvenance, InvoiceDraft, InvoiceDraftLine
from ..invoice_evidence_operation_dtos import InvoiceDraftProjectionV1

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SESSION_CLIENT = UUID("5aa00000-0000-4000-8000-0000000000dd")
_SOURCE = "a" * 64
_EVIDENCE = "e" * 16
_MCP = OperationFrontendProjection.MCP
_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_DEFINITION_ID = extract_operation.LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID

_THIS_MACHINE = "http://127.0.0.1:11434/api/chat"
_ANOTHER_MACHINE = "http://reader.example.invalid:11434/api/chat"

_SUPPLIER_NAME = "SUMINISTROS SINTETICOS DEL NORTE SL"
_INVOICE_NUMBER = "SYN-2026-000417"
_LINE_DESCRIPTION = "Mantenimiento trimestral de instalaciones sinteticas"
_SUPPLIER_ANCHOR = "Emisor: SUMINISTROS SINTETICOS DEL NORTE SL (impreso)"
_DOCUMENT_TEXTS = (_SUPPLIER_NAME, _INVOICE_NUMBER, _LINE_DESCRIPTION, _SUPPLIER_ANCHOR)


def _draft_with_document_text() -> InvoiceDraft:
    return InvoiceDraft(
        supplier_name=_SUPPLIER_NAME,
        invoice_number=_INVOICE_NUMBER,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        lines=(
            InvoiceDraftLine(
                description=_LINE_DESCRIPTION,
                taxable_base=Decimal("100.00"),
                iva_rate=Decimal("21"),
                iva_amount=Decimal("21.00"),
            ),
        ),
        provenance=(
            FieldProvenance(
                field="supplier_name",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor=_SUPPLIER_ANCHOR,
            ),
        ),
        raw_text_length=2_048,
    )


class _Recorder:
    """The executor's events, cancellation fence and result operand, kept for the assertions."""

    def __init__(self) -> None:
        self.effects: list[OperationEffect] = []
        self.result: BaseModel | None = None

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        yield

    async def phase(self, code: str) -> None:
        assert code == _DEFINITION_ID

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)

    async def put(self, value: BaseModel, *, written_at: object) -> str:
        del written_at
        self.result = value
        return "b" * 64


def _context(recorder: _Recorder, authority: PinnedAuthorityOperation) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(
                definition_id=_DEFINITION_ID, subject_ref=profile_operation_subject(str(_PROFILE))
            ),
            events=recorder,
            cancellation=recorder,
            operands=recorder,
            authority_operation=authority,
        ),
    )


def _session_host(frontend: OperationFrontendProjection) -> OperationExecutionCallerReader:
    """What a session host answers for an extraction it admitted on ``frontend``."""

    def read(identity: OperationIdentity) -> OperationExecutionCaller:
        assert identity.definition_id == _DEFINITION_ID
        return OperationExecutionCaller(frontend=frontend, session_kind=SessionKind.ATTENDED, client_id=_SESSION_CLIENT)

    return read


def _ports_factory(reader_endpoint: str, opened: list[str]) -> operation_ports.InvoiceEvidenceOperationPortsFactory:
    """Bind ports whose only live member is the settings that name the on-host reader's endpoint."""

    def make(
        *,
        bucket_id: str,
        before_consent_save: Callable[[], None] | None = None,
        after_consent_save: Callable[[bool], None] | None = None,
    ) -> operation_ports.InvoiceEvidenceOperationPorts:
        assert bucket_id == str(_PROFILE)
        assert before_consent_save is None and after_consent_save is None
        opened.append(bucket_id)

        def mint(provider: LLMProvider, acknowledged: bool, surface: str, content_sha256: str) -> EvidenceConsentProof:
            raise AssertionError(f"an on-host read minted a consent for {provider.value}")

        return operation_ports.InvoiceEvidenceOperationPorts(
            bucket_id=bucket_id,
            settings=Settings.model_construct(cadrumo_llm_ollama_chat_url=reader_endpoint),
            evidence_ports=cast(operation_ports.LedgerEvidencePorts, object()),
            extraction_ports=cast(InvoiceDraftExtractionPorts, object()),
            catalogue_creation_ports=cast(operation_ports.CatalogueCreationPorts, object()),
            invoice_confirmation_ports=cast(operation_ports.InvoiceConfirmationPorts, object()),
            counterparty_establishment_repository=cast(
                operation_ports.CounterpartyEstablishmentRepositoryProtocol, object()
            ),
            mint_consent=mint,
        )

    return make


def _payload(*, off_host: bool) -> extract_operation.LedgerEvidenceExtractRequest:
    return extract_operation.LedgerEvidenceExtractRequest(
        profile_id=_PROFILE,
        evidence_id=_EVIDENCE if off_host else None,
        attachment_id=None if off_host else _SOURCE,
        off_host_provider=LLMProvider.ANTHROPIC if off_host else None,
        acknowledge_off_host=off_host,
    )


def _request(*, off_host: bool = False) -> OperationRequest[extract_operation.LedgerEvidenceExtractRequest]:
    return OperationRequest[extract_operation.LedgerEvidenceExtractRequest](
        definition_id=_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=_payload(off_host=off_host),
    )


def _access_request(*, off_host: bool = False) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=_payload(off_host=off_host),
    )


def _bind_the_document_reading(monkeypatch: pytest.MonkeyPatch, readings: list[str]) -> None:
    """Stand in for the stored profile and for the reading of the document's bytes.

    The executor's own decisions are what these tests judge: whether it reads
    at all, and what of the reading it seals. The reading is a fixed draft.
    """
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_ports, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(extract_operation, "resolve_invoice_evidence_authority_legends", lambda _context: ())

    def read(**kwargs: object) -> InvoiceDraft:
        assert kwargs["off_host_provider"] is None and kwargs["consent_token"] is None
        readings.append(str(kwargs["attachment_id"]))
        return _draft_with_document_text()

    monkeypatch.setattr(extract_operation, "extract_invoice_draft_from_evidence", read)


def _sealed(recorder: _Recorder) -> extract_operation.LedgerEvidenceExtractProjection:
    assert isinstance(recorder.result, extract_operation.LedgerEvidenceExtractExecutionResult)
    return recorder.result.result


# ---------------------------------------------------------------------------
# The registered resolver
# ---------------------------------------------------------------------------


def _unopened_ports(**_kwargs: object) -> operation_ports.InvoiceEvidenceOperationPorts:
    raise AssertionError("access resolution opened the evidence ports")


def _registry() -> tuple[OperationRegistry, OperationPublicDefinitionRegistrationV1]:
    definition = extract_operation.build_ledger_evidence_extract_definition(_unopened_ports)
    registration = extract_operation.build_ledger_evidence_extract_registration(definition)
    return OperationRegistry(definitions=(definition,), public_registrations=(registration,)), registration


def _access_context(
    registration: OperationPublicDefinitionRegistrationV1,
    *,
    frontend: OperationFrontendProjection,
    action: AccessAction = AccessAction.SUBMIT,
) -> OperationAccessContext:
    return OperationAccessContext(
        profile_id=_PROFILE,
        destination_id=_SESSION_CLIENT,
        action=action,
        frontend=frontend,
        contract=registration.contract,
        published_authority=Availability.AVAILABLE,
    )


def test_the_extraction_lists_every_frontend_and_records_the_off_host_read_as_the_persons() -> None:
    _, registration = _registry()
    decision = mcp_admission_decision(_DEFINITION_ID)

    assert registration.contract.permitted_frontends == frozenset(OperationFrontendProjection)
    assert decision.ruling is McpRuling.ADMITTED
    assert decision.prerequisites == frozenset()
    assert decision.sensitive_actions == ("off_host",)


@pytest.mark.parametrize("frontend", sorted(OperationFrontendProjection))
def test_an_on_host_read_is_admitted_on_every_frontend_without_a_commit_door(
    frontend: OperationFrontendProjection,
) -> None:
    registry, registration = _registry()
    request = _access_request()

    resolved = resolve_operation_access(
        registry=registry, request=request, context=_access_context(registration, frontend=frontend)
    )
    person = resolve_operation_access(
        registry=registry, request=request, context=_access_context(registration, frontend=_CLI)
    )

    assert resolved.request.frontend is frontend
    assert resolved.policy == person.policy
    assert resolved.policy.requires_human is False
    assert AccessAction.COMMIT not in resolved.policy.actions


@pytest.mark.parametrize(
    "action",
    [AccessAction.SUBMIT, AccessAction.START, AccessAction.COMMIT, AccessAction.OBSERVE, AccessAction.RESULT],
)
def test_an_off_host_read_is_refused_to_an_mcp_session_at_every_access(action: AccessAction) -> None:
    registry, registration = _registry()
    request = _access_request(off_host=True)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        resolve_operation_access(
            registry=registry, request=request, context=_access_context(registration, frontend=_MCP, action=action)
        )

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


@pytest.mark.parametrize("frontend", [_CLI, _TUI])
def test_an_off_host_read_stays_open_to_a_person_behind_its_commit_door(
    frontend: OperationFrontendProjection,
) -> None:
    registry, registration = _registry()
    request = _access_request(off_host=True)

    resolved = resolve_operation_access(
        registry=registry, request=request, context=_access_context(registration, frontend=frontend)
    )

    assert AccessAction.COMMIT in resolved.policy.actions


# ---------------------------------------------------------------------------
# The executor, for an agent and for a person
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reader_endpoint",
    [_THIS_MACHINE, "http://localhost:11434/api/chat", "http://[::1]:11434/api/chat"],
)
async def test_an_agents_read_on_this_machine_seals_the_summary_and_no_text_from_the_document(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation, reader_endpoint: str
) -> None:
    recorder, readings, opened = _Recorder(), list[str](), list[str]()
    _bind_the_document_reading(monkeypatch, readings)
    executor = extract_operation.LedgerEvidenceExtractExecutor(
        _ports_factory(reader_endpoint, opened), execution_caller_reader=_session_host(_MCP)
    )

    await executor.execute(_request(), _context(recorder, operation))

    sealed = _sealed(recorder)
    full = InvoiceDraftProjectionV1.from_draft(_draft_with_document_text())
    assert readings == [_SOURCE]
    assert recorder.effects == [OperationEffect.NONE]
    assert sealed.draft is None
    summary = sealed.draft_summary
    assert summary is not None
    assert summary.profile_id == _PROFILE
    assert summary.evidence_reference == _SOURCE
    assert summary.extractor == "extract_invoice_draft_from_evidence"
    assert summary.text_withheld is True
    assert summary.withheld_text_fields == ("supplier_name", "invoice_number")
    assert (summary.taxable_base, summary.iva_rate, summary.iva_amount, summary.grand_total) == (
        full.taxable_base,
        full.iva_rate,
        full.iva_amount,
        full.grand_total,
    )
    (line,) = summary.lines
    assert line.description_withheld is True and line.taxable_base == full.lines[0].taxable_base
    (supplier,) = summary.fields
    assert (supplier.field, supplier.origin, supplier.anchor_withheld) == (
        "supplier_name",
        FieldOrigin.TEXT_LAYER,
        True,
    )
    assert sealed.source_sha256 == _SOURCE
    assert sealed.draft_review_sha256 == invoice_draft_review_sha256(_draft_with_document_text())
    released = recorder.result.model_dump_json() if recorder.result is not None else ""
    assert released
    assert [text for text in _DOCUMENT_TEXTS if text in released] == []
    with pytest.raises(ValueError, match="sealed for an agent"):
        sealed.person_draft()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "reader_endpoint",
    [
        _ANOTHER_MACHINE,
        "http://192.0.2.10:11434/api/chat",
        "http://127.0.0.1@reader.example.invalid:11434/api/chat",
        "http://localhost.reader.example.invalid/api/chat",
        "http://[::1/api/chat",
        "not an address",
    ],
)
async def test_an_agents_read_is_refused_before_any_byte_is_read_while_the_reader_is_not_this_machine(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation, reader_endpoint: str
) -> None:
    recorder, readings, opened = _Recorder(), list[str](), list[str]()
    _bind_the_document_reading(monkeypatch, readings)
    executor = extract_operation.LedgerEvidenceExtractExecutor(
        _ports_factory(reader_endpoint, opened), execution_caller_reader=_session_host(_MCP)
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await executor.execute(_request(), _context(recorder, operation))

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert readings == []
    assert recorder.result is None


@pytest.mark.asyncio
@pytest.mark.parametrize("frontend", [_CLI, _TUI])
@pytest.mark.parametrize("reader_endpoint", [_THIS_MACHINE, _ANOTHER_MACHINE])
async def test_a_persons_read_seals_the_full_draft_wherever_the_person_pointed_the_reader(
    monkeypatch: pytest.MonkeyPatch,
    operation: PinnedAuthorityOperation,
    frontend: OperationFrontendProjection,
    reader_endpoint: str,
) -> None:
    recorder, readings, opened = _Recorder(), list[str](), list[str]()
    _bind_the_document_reading(monkeypatch, readings)
    executor = extract_operation.LedgerEvidenceExtractExecutor(
        _ports_factory(reader_endpoint, opened), execution_caller_reader=_session_host(frontend)
    )

    await executor.execute(_request(), _context(recorder, operation))

    sealed = _sealed(recorder)
    assert readings == [_SOURCE]
    assert sealed.draft_summary is None
    assert sealed.person_draft() == InvoiceDraftProjectionV1.from_draft(_draft_with_document_text())
    assert sealed.person_draft().supplier_name == _SUPPLIER_NAME


@pytest.mark.asyncio
async def test_an_agents_off_host_request_is_refused_by_the_executor_before_a_port_is_opened(
    monkeypatch: pytest.MonkeyPatch, operation: PinnedAuthorityOperation
) -> None:
    recorder, readings, opened = _Recorder(), list[str](), list[str]()
    _bind_the_document_reading(monkeypatch, readings)
    executor = extract_operation.LedgerEvidenceExtractExecutor(
        _ports_factory(_THIS_MACHINE, opened), execution_caller_reader=_session_host(_MCP)
    )

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await executor.execute(_request(off_host=True), _context(recorder, operation))

    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED
    assert (opened, readings, recorder.effects, recorder.result) == ([], [], [], None)


def test_a_result_carries_the_draft_or_its_summary_and_never_neither() -> None:
    with pytest.raises(ValidationError, match="never both or neither"):
        extract_operation.LedgerEvidenceExtractProjection(
            profile_id=_PROFILE,
            attachment_id=_SOURCE,
            source_sha256=_SOURCE,
            draft_review_sha256=_SOURCE,
            consent_audit_effect=OperationEffect.NONE,
        )
