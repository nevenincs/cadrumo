"""Invoice extraction effects follow actual consent saves, including later refusal."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest

from ....core.config import Settings
from ....core.config_support import LLMProvider
from ....core.operations import OperationEffect, profile_operation_subject
from ...operations.models import OperationRequest
from ...operations.owner import OperationExecutorContext
from .. import invoice_evidence_extract_operation as extract_operation
from .. import invoice_evidence_operation as operation
from ..invoice_draft_extraction_ports import EvidenceConsentProof, InvoiceDraftExtractionPorts
from ..invoice_draft_records import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]
_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_SOURCE = "a" * 64


class _Recorder:
    def __init__(self) -> None:
        self.timeline: list[tuple[str, object]] = []
        self.active = False
        self.result: object | None = None

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncIterator[None]:
        assert not self.active
        self.active = True
        self.timeline.append(("enter", asyncio.current_task()))
        try:
            yield
        finally:
            self.timeline.append(("exit", asyncio.current_task()))
            self.active = False

    async def phase(self, code: str) -> None:
        self.timeline.append(("phase", code))

    async def effect(self, effect: OperationEffect) -> None:
        self.timeline.append(("effect", effect))

    async def put(self, value: object, *, written_at: object) -> str:
        assert not self.active
        self.result = value
        return "b" * 64


def _context(recorder: _Recorder) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(
                definition_id=extract_operation.LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            events=recorder,
            cancellation=recorder,
            operands=recorder,
            authority_operation=object(),
        ),
    )


def _factory(
    recorder: _Recorder,
    hooks: list[tuple[Callable[[], None] | None, Callable[[bool], None] | None]],
) -> operation.InvoiceEvidenceOperationPortsFactory:
    def make(
        *,
        bucket_id: str,
        before_consent_save: Callable[[], None] | None = None,
        after_consent_save: Callable[[bool], None] | None = None,
    ) -> operation.InvoiceEvidenceOperationPorts:
        assert bucket_id == str(_PROFILE)
        hooks.append((before_consent_save, after_consent_save))

        def mint(provider: LLMProvider, acknowledged: bool, surface: str, content_sha256: str) -> EvidenceConsentProof:
            assert provider is LLMProvider.ANTHROPIC
            assert acknowledged and surface == "runtime:ledger.evidence.extract"
            assert content_sha256 == _SOURCE
            recorder.timeline.append(("mint", content_sha256))
            return cast(EvidenceConsentProof, SimpleNamespace(evidence_content_address=content_sha256))

        return operation.InvoiceEvidenceOperationPorts(
            bucket_id=bucket_id,
            settings=cast(Settings, object()),
            evidence_ports=cast(operation.LedgerEvidencePorts, object()),
            extraction_ports=cast(InvoiceDraftExtractionPorts, object()),
            catalogue_creation_ports=cast(operation.CatalogueCreationPorts, object()),
            invoice_confirmation_ports=cast(operation.InvoiceConfirmationPorts, object()),
            counterparty_establishment_repository=cast(operation.CounterpartyEstablishmentRepositoryProtocol, object()),
            mint_consent=mint,
        )

    return make


def _request(*, off_host: bool) -> OperationRequest[extract_operation.LedgerEvidenceExtractRequest]:
    payload = extract_operation.LedgerEvidenceExtractRequest(
        profile_id=_PROFILE,
        evidence_id="e" * 16 if off_host else None,
        attachment_id=None if off_host else _SOURCE,
        off_host_provider=LLMProvider.ANTHROPIC if off_host else None,
        acknowledge_off_host=off_host,
    )
    return OperationRequest[extract_operation.LedgerEvidenceExtractRequest](
        definition_id=extract_operation.LEDGER_EVIDENCE_EXTRACT_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=payload,
    )


@pytest.mark.asyncio
async def test_on_host_executor_captures_full_draft_with_no_consent_write(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder = _Recorder()
    hooks: list[tuple[Callable[[], None] | None, Callable[[bool], None] | None]] = []
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(extract_operation, "resolve_invoice_evidence_authority_legends", lambda _context: ())

    def read(**kwargs: object) -> InvoiceDraft:
        assert kwargs["off_host_provider"] is None
        assert kwargs["consent_token"] is None
        assert not recorder.active
        recorder.timeline.append(("reader", "on-host"))
        return InvoiceDraft(invoice_number="A-1")

    monkeypatch.setattr(extract_operation, "extract_invoice_draft_from_evidence", read)
    reference = await extract_operation.LedgerEvidenceExtractExecutor(_factory(recorder, hooks)).execute(
        _request(off_host=False), _context(recorder)
    )
    assert reference == "b" * 64
    assert hooks == [(None, None)]
    assert [(kind, value) for kind, value in recorder.timeline if kind == "effect"] == [
        ("effect", OperationEffect.NONE)
    ]
    assert isinstance(recorder.result, extract_operation.LedgerEvidenceExtractExecutionResult)
    assert recorder.result.result.consent_audit_effect is OperationEffect.NONE
    assert recorder.result.result.draft.invoice_number == "A-1"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("save_succeeded", "later_refusal"),
    [(False, False), (True, True), (True, False)],
)
async def test_off_host_executor_reports_the_actual_append_effect(
    monkeypatch: pytest.MonkeyPatch, save_succeeded: bool, later_refusal: bool
) -> None:
    recorder = _Recorder()
    hooks: list[tuple[Callable[[], None] | None, Callable[[bool], None] | None]] = []
    monkeypatch.setattr("cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(extract_operation, "resolve_invoice_evidence_authority_legends", lambda _context: ())
    monkeypatch.setattr(
        extract_operation.PurchaseInvoiceEvidenceService,
        "view",
        lambda _self, *, bucket_id, evidence_id: SimpleNamespace(
            bucket_id=bucket_id, evidence_id=evidence_id, attachment_id=_SOURCE, source_sha256=_SOURCE
        ),
    )

    def read(**kwargs: object) -> InvoiceDraft:
        assert kwargs["off_host_provider"] is LLMProvider.ANTHROPIC
        assert cast(EvidenceConsentProof, kwargs["consent_token"]).evidence_content_address == _SOURCE
        before, after = hooks[0]
        assert before is not None and after is not None
        before()
        assert recorder.active
        recorder.timeline.append(("secure-save", save_succeeded))
        after(save_succeeded)
        assert not recorder.active
        if later_refusal:
            recorder.timeline.append(("later-reader-refusal", True))
            raise RuntimeError("reader refused after the consent append")
        if not save_succeeded:
            recorder.timeline.append(("dispatch-refused", True))
            raise RuntimeError("consent append failed before dispatch")
        recorder.timeline.append(("reader", "off-host"))
        return InvoiceDraft(invoice_number="A-2")

    monkeypatch.setattr(extract_operation, "extract_invoice_draft_from_evidence", read)
    executor = extract_operation.LedgerEvidenceExtractExecutor(_factory(recorder, hooks))
    if later_refusal or not save_succeeded:
        with pytest.raises(RuntimeError, match=r"reader refused|consent append failed"):
            await executor.execute(_request(off_host=True), _context(recorder))
    else:
        reference = await executor.execute(_request(off_host=True), _context(recorder))
        assert reference == "b" * 64

    expected = [OperationEffect.NONE, OperationEffect.UNKNOWN]
    if save_succeeded:
        expected.append(OperationEffect.UPDATED)
    assert [value for kind, value in recorder.timeline if kind == "effect"] == expected
    assert [kind for kind, _ in recorder.timeline if kind in {"enter", "secure-save", "exit"}] == [
        "enter",
        "secure-save",
        "exit",
    ]
    assert recorder.timeline.index(("mint", _SOURCE)) < recorder.timeline.index(
        ("enter", next(value for kind, value in recorder.timeline if kind == "enter"))
    )
    if later_refusal or not save_succeeded:
        assert recorder.result is None
    else:
        assert isinstance(recorder.result, extract_operation.LedgerEvidenceExtractExecutionResult)
        assert recorder.result.result.consent_audit_effect is OperationEffect.UPDATED
        assert recorder.result.result.draft.invoice_number == "A-2"
