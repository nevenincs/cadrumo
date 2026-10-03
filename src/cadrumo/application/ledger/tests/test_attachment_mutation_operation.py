"""Attachment operation receipts preserve the canonical action's effect boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel

from ....application.ledger import attachment_mutation_operation as operation_module
from ....application.ledger.action_ports import LedgerActionPorts
from ....application.ledger.attachment_mutation_operation import (
    LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE,
    LEDGER_DETACH_OPERATION_DEFINITION_ID,
    LedgerAttachExecutor,
    LedgerAttachmentExecutionResult,
    LedgerAttachmentProjection,
    LedgerAttachRequest,
    LedgerDetachExecutor,
    LedgerDetachRequest,
)
from ....application.operations import profile_guard
from ....application.operations.models import OperationRequest
from ....application.operations.owner import OperationExecutorContext
from ....application.operations.refusal_evidence import OperationRefusalEvidence
from ....application.review.filter import LedgerReviewStatus
from ....application.user_profile.access_contracts import AccessDenialCode
from ....application.user_profile.access_errors import ProfileAccessRefusedError
from ....core.operations import OperationEffect, profile_operation_subject
from ....domain.attachments.errors import AttachmentNotFoundError
from ....domain.transactions.errors import TransactionValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRANSACTION_ID = "a" * 64
_ATTACHMENT_ID = "b" * 64
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)


def _projection(
    *,
    operation_id: operation_module.LedgerAttachmentOperationId = LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    attachment_ids: tuple[str, ...] = (_ATTACHMENT_ID,),
) -> LedgerAttachmentProjection:
    return LedgerAttachmentProjection(
        profile_id=_PROFILE,
        operation_id=operation_id,
        transaction=operation_module.LedgerTransactionProjection(
            transaction_id=_TRANSACTION_ID,
            date="2026-05-08",
            booked_date="2026-05-08",
            value_date=None,
            amount="1.00",
            currency="EUR",
            direction="outgoing",
            counterparty="Supplier SL",
            description="Invoice payment",
            business_classification="not_yet_processed",
            business_pct=None,
            category_id=None,
            taxable_base=None,
            iva_rate=None,
            iva_amount=None,
            iva_category=None,
            counterparty_country=None,
            counterparty_identification_state=None,
            irpf_category=None,
            m210_income_classification=None,
            usage_ratio_id=None,
            prorrata_reference=None,
            purchase_invoice_evidence_id=None,
            invoice_id=None,
            attachment_ids=attachment_ids,
            notes="",
            lifecycle_state="active",
            classified_by="manual",
            classified_at=None,
            classification_reason="",
            classification_confidence=None,
            source_jurisdiction=None,
            value_in_eur=None,
            fx_rate=None,
            created_at=_AT.isoformat(),
            modified_at=_AT.isoformat(),
        ),
        review_status=LedgerReviewStatus.PENDING,
        bucket_event_ids=("e" * 64,),
    )


def _context(
    effects: list[OperationEffect],
    *,
    profile_id: UUID = _PROFILE,
    operation_id: operation_module.LedgerAttachmentOperationId = LEDGER_ATTACH_OPERATION_DEFINITION_ID,
    identity_definition_id: operation_module.LedgerAttachmentOperationId | None = None,
    phase_calls: list[str] | None = None,
):
    active = False

    class Cancellation:
        @asynccontextmanager
        async def irreversible_section(self):
            nonlocal active
            assert not active
            active = True
            try:
                yield
            finally:
                active = False

    class Events:
        async def phase(self, phase: str) -> None:
            if phase_calls is not None:
                phase_calls.append(phase)
            assert phase == operation_id

        async def effect(self, effect: OperationEffect) -> None:
            if effect is OperationEffect.NONE and not effects:
                assert not active
            else:
                assert active
            effects.append(effect)

    class Operands:
        async def put(self, operand: BaseModel, *, written_at: datetime) -> str:
            assert not active
            assert written_at.tzinfo is not None
            assert isinstance(operand, LedgerAttachmentExecutionResult)
            return "d" * 64

    subject = profile_operation_subject(str(profile_id))
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(
                definition_id=operation_id if identity_definition_id is None else identity_definition_id,
                subject_ref=subject,
            ),
            authority_operation=object(),
            cancellation=Cancellation(),
            events=Events(),
            operands=Operands(),
        ),
    )


def _request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_ATTACH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerAttachRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION_ID[:12],
            attachment_ids=(_ATTACHMENT_ID,),
        ),
    )


def _detach_request() -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=LEDGER_DETACH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerDetachRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION_ID[:12],
            attachment_ids=(_ATTACHMENT_ID,),
        ),
    )


def _ports_factory_for(context: OperationExecutorContext):
    class TransactionRepository:
        bucket_id = str(_PROFILE)

        def load(self):
            return SimpleNamespace(transactions={_TRANSACTION_ID: object()})

    return lambda *, bucket_id, operation: cast(
        LedgerActionPorts,
        SimpleNamespace(
            operation=operation,
            transaction_repository=TransactionRepository(),
            invoice_repository=SimpleNamespace(bucket_id=bucket_id),
            work_unit_repository=SimpleNamespace(bucket_id=bucket_id),
            calculation_repository=SimpleNamespace(bucket_id=bucket_id),
        ),
    )


@pytest.mark.asyncio
async def test_attach_marks_unknown_then_updated_and_publishes_outside_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects: list[OperationEffect] = []
    context = _context(effects)
    action_calls: list[dict[str, object]] = []

    def attach(**kwargs: object) -> object:
        action_calls.append(kwargs)
        assert effects == [OperationEffect.UNKNOWN]
        return SimpleNamespace(bucket_event_ids=("e" * 64,))

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, "attach_manual_transaction_evidence", attach)
    monkeypatch.setattr(operation_module, "_operation_projection", lambda *_args: _projection())

    executor = LedgerAttachExecutor(_ports_factory_for(context))
    completed = await executor.execute(_request(), context)

    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert isinstance(completed, str)
    assert action_calls[0]["bucket_id"] == str(_PROFILE)
    assert action_calls[0]["transaction_id"] == _TRANSACTION_ID
    assert action_calls[0]["attachment_ids"] == (_ATTACHMENT_ID,)


@pytest.mark.asyncio
async def test_attach_canonical_validation_refusal_restores_none_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects: list[OperationEffect] = []
    context = _context(effects)

    def attach(**_kwargs: object) -> object:
        raise TransactionValidationError("attachment reference is not valid")

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, "attach_manual_transaction_evidence", attach)

    executor = LedgerAttachExecutor(_ports_factory_for(context))
    completed = await executor.execute(_request(), context)

    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    assert isinstance(completed, OperationRefusalEvidence)
    assert completed.refusal_code == LEDGER_ATTACHMENT_VALIDATION_REFUSAL_CODE
    assert completed.detail_ref == "d" * 64


@pytest.mark.asyncio
async def test_attach_reverse_manifest_failure_is_known_partial_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects: list[OperationEffect] = []
    context = _context(effects)

    def attach(**_kwargs: object) -> object:
        raise AttachmentNotFoundError("manifest disappeared after transaction commit")

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, "attach_manual_transaction_evidence", attach)

    executor = LedgerAttachExecutor(_ports_factory_for(context))
    with pytest.raises(AttachmentNotFoundError):
        await executor.execute(_request(), context)

    assert effects == [OperationEffect.UNKNOWN, OperationEffect.PARTIAL]


@pytest.mark.asyncio
async def test_detach_marks_unknown_then_updated_and_publishes_outside_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects: list[OperationEffect] = []
    context = _context(effects, operation_id=LEDGER_DETACH_OPERATION_DEFINITION_ID)
    action_calls: list[dict[str, object]] = []

    def detach(**kwargs: object) -> object:
        action_calls.append(kwargs)
        assert effects == [OperationEffect.UNKNOWN]
        return SimpleNamespace(bucket_event_ids=("e" * 64,))

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, "detach_manual_transaction_attachments", detach)
    monkeypatch.setattr(
        operation_module,
        "_operation_projection",
        lambda profile_id, operation_id, _result: _projection(
            operation_id=operation_id,
            attachment_ids=(),
        ),
    )

    executor = LedgerDetachExecutor(_ports_factory_for(context))
    completed = await executor.execute(_detach_request(), context)

    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert isinstance(completed, str)
    assert action_calls[0]["bucket_id"] == str(_PROFILE)
    assert action_calls[0]["transaction_id"] == _TRANSACTION_ID
    assert action_calls[0]["attachment_ids"] == (_ATTACHMENT_ID,)


@pytest.mark.asyncio
async def test_attach_refuses_matching_wrong_definition_before_phase_or_ports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    effects: list[OperationEffect] = []
    phase_calls: list[str] = []
    context = _context(
        effects,
        identity_definition_id=LEDGER_DETACH_OPERATION_DEFINITION_ID,
        phase_calls=phase_calls,
    )
    request = _request().model_copy(update={"definition_id": LEDGER_DETACH_OPERATION_DEFINITION_ID})
    ports_calls: list[str] = []

    def active_bucket_must_not_be_read() -> str:
        raise AssertionError("expected-definition refusal must precede the shared profile guard")

    def unexpected_ports_factory(*, bucket_id: str, operation: object) -> LedgerActionPorts:
        _ = operation
        ports_calls.append(bucket_id)
        raise AssertionError("expected-definition refusal must precede port composition")

    monkeypatch.setattr(profile_guard, "require_active_bucket_id", active_bucket_must_not_be_read)

    with pytest.raises(ProfileAccessRefusedError) as refused:
        await LedgerAttachExecutor(unexpected_ports_factory).execute(request, context)

    assert refused.value.reason is AccessDenialCode.PROFILE_MISMATCH
    assert phase_calls == []
    assert ports_calls == []
    assert effects == []
