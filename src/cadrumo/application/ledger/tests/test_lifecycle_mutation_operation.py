"""Lifecycle operation receipts retain the canonical co-commit boundary."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import UUID

import pytest
from pydantic import BaseModel, ValidationError

from ....application.ledger import lifecycle_mutation_operation as operation_module
from ....application.ledger.action_ports import LedgerActionPorts, LedgerActionPortsFactory
from ....application.ledger.lifecycle_mutation_operation import (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
    LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LedgerLifecycleExecutionResult,
    LedgerLifecycleMutationProjection,
    LedgerLifecycleMutationRequest,
    LedgerLifecycleOperationId,
    LedgerLifecycleOperationResult,
    LedgerLifecycleValidationProjection,
)
from ....application.ledger.protocols import (
    BucketEventHistoryCoCommitWriterProtocol,
    InvoiceCatalogueCoCommitWriterProtocol,
    TransactionCatalogueCoCommitWriterProtocol,
)
from ....application.ledger.transaction_projection import LedgerTransactionProjection
from ....application.ledger.usage_ratio_repository import UsageRatioProfileLoader
from ....application.operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ....application.operations.owner import OperationExecutorContext
from ....application.operations.refusal_evidence import OperationRefusalEvidence
from ....application.review.filter import LedgerReviewStatus
from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.attachments.protocols import AttachmentStoreProtocol
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.protocols import CalculationRevisionCatalogueRepositoryProtocol
from ....domain.modelos.work_unit_repository import WorkUnitCatalogueRepositoryProtocol
from ....domain.transactions.errors import TransactionIdPrefixError, TransactionValidationError
from ....domain.transactions.models import TransactionCatalogue
from ....domain.usage_ratios.model import UsageRatioProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = UUID("5aa00000-0000-4000-8000-0000000000aa")
_TRANSACTION_ID = "a" * 64
_EVENT_ID = "e" * 64
_AT = datetime(2026, 5, 8, 10, 15, tzinfo=UTC)
_OPERATIONS: tuple[LedgerLifecycleOperationId, ...] = (
    LEDGER_ARCHIVE_OPERATION_DEFINITION_ID,
    LEDGER_STASH_OPERATION_DEFINITION_ID,
    LEDGER_RESTORE_OPERATION_DEFINITION_ID,
    LEDGER_EXCLUDE_OPERATION_DEFINITION_ID,
)


def _projection(operation_id: LedgerLifecycleOperationId) -> LedgerLifecycleMutationProjection:
    return LedgerLifecycleMutationProjection(
        profile_id=_PROFILE,
        operation_id=operation_id,
        transaction=LedgerTransactionProjection(
            transaction_id=_TRANSACTION_ID,
            date="2026-05-08",
            booked_date="2026-05-08",
            value_date=None,
            amount="123.45",
            currency="EUR",
            direction="OUTGOING",
            counterparty="Supplier SL",
            description="Invoice payment",
            business_classification=(
                "REVIEWED_EXCLUDED" if operation_id == LEDGER_EXCLUDE_OPERATION_DEFINITION_ID else "BUSINESS"
            ),
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
            attachment_ids=(),
            notes="",
            lifecycle_state=(
                "ARCHIVED"
                if operation_id == LEDGER_ARCHIVE_OPERATION_DEFINITION_ID
                else "STASHED"
                if operation_id == LEDGER_STASH_OPERATION_DEFINITION_ID
                else "ACTIVE"
            ),
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
        review_status=(
            LedgerReviewStatus.EXCLUDED
            if operation_id == LEDGER_EXCLUDE_OPERATION_DEFINITION_ID
            else LedgerReviewStatus.REVIEWED
        ),
        bucket_event_ids=(_EVENT_ID,),
    )


def _context(
    effects: list[OperationEffect],
    *,
    operation_id: LedgerLifecycleOperationId,
    stored: list[LedgerLifecycleExecutionResult],
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
            if not isinstance(operand, LedgerLifecycleExecutionResult):
                raise AssertionError("lifecycle executor stored an unexpected operand")
            stored.append(operand)
            return "d" * 64

    subject = profile_operation_subject(str(_PROFILE))
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(definition_id=operation_id, subject_ref=subject),
            authority_operation=object(),
            cancellation=Cancellation(),
            events=Events(),
            operands=Operands(),
        ),
    )


def _ports_factory(
    context: OperationExecutorContext,
) -> LedgerActionPortsFactory:
    pin: PinnedAuthorityOperation = context.authority_operation

    class TransactionRepository:
        bucket_id = str(_PROFILE)

        def load(self):
            return SimpleNamespace(transactions={_TRANSACTION_ID: object()})

        def save_with_secure_object_writes(self, _catalogue: object, _extra_writes: object) -> None:
            return None

        def replace_if_current_with_secure_object_writes(
            self,
            _current: object,
            _replacement: object,
            _extra_writes: object,
        ) -> None:
            return None

        def save(self, _catalogue: object) -> None:
            return None

    bucket_repo = SimpleNamespace(bucket_id=str(_PROFILE))

    def build(*, bucket_id: str, operation: PinnedAuthorityOperation) -> LedgerActionPorts:
        assert bucket_id == str(_PROFILE)
        assert operation is pin
        return LedgerActionPorts(
            operation=operation,
            transaction_repository=cast(TransactionCatalogueCoCommitWriterProtocol, TransactionRepository()),
            bucket_event_repository=cast(BucketEventHistoryCoCommitWriterProtocol, bucket_repo),
            invoice_repository=cast(InvoiceCatalogueCoCommitWriterProtocol, bucket_repo),
            attachment_store=cast(AttachmentStoreProtocol, object()),
            usage_ratio_profile=cast(UsageRatioProfile, object()),
            usage_ratio_profile_loader=cast(UsageRatioProfileLoader, object()),
            work_unit_repository=cast(WorkUnitCatalogueRepositoryProtocol, bucket_repo),
            calculation_repository=cast(CalculationRevisionCatalogueRepositoryProtocol, bucket_repo),
            purchase_invoice_evidence_records=(),
        )

    return build


def _request(operation_id: LedgerLifecycleOperationId) -> OperationRequest[BaseModel]:
    return OperationRequest[BaseModel](
        definition_id=operation_id,
        subject_ref=profile_operation_subject(str(_PROFILE)),
        payload=LedgerLifecycleMutationRequest(
            profile_id=_PROFILE,
            transaction_id=_TRANSACTION_ID[:12],
            actor="operator",
            reason="test reason",
        ),
    )


@pytest.mark.parametrize(("operation_id", "method_name"), [(key, key.rsplit(".", 1)[1]) for key in _OPERATIONS])
@pytest.mark.asyncio
async def test_canonical_success_is_fenced_and_result_is_published_afterward(
    monkeypatch: pytest.MonkeyPatch,
    operation_id: LedgerLifecycleOperationId,
    method_name: str,
) -> None:
    effects: list[OperationEffect] = []
    stored: list[LedgerLifecycleExecutionResult] = []
    context = _context(effects, operation_id=operation_id, stored=stored)
    action_calls: list[dict[str, object]] = []

    def action(**kwargs: object) -> object:
        action_calls.append(kwargs)
        ports = kwargs.get("ports")
        repository: object = (
            cast(LedgerActionPorts, ports).transaction_repository
            if ports is not None
            else kwargs.get("transaction_repository")
        )
        assert effects == [OperationEffect.UNKNOWN]
        cast(TransactionCatalogueCoCommitWriterProtocol, repository).save_with_secure_object_writes(
            cast(TransactionCatalogue, object()),
            (),
        )
        return SimpleNamespace(bucket_event_ids=(_EVENT_ID,))

    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, method_name + "_manual_transaction", action, raising=False)
    if operation_id == LEDGER_EXCLUDE_OPERATION_DEFINITION_ID:
        monkeypatch.setattr(operation_module, "mark_transaction_reviewed_excluded", action)
    monkeypatch.setattr(operation_module, "_operation_projection", lambda *_args: _projection(operation_id))

    executor_type = {
        LEDGER_ARCHIVE_OPERATION_DEFINITION_ID: operation_module.LedgerArchiveExecutor,
        LEDGER_STASH_OPERATION_DEFINITION_ID: operation_module.LedgerStashExecutor,
        LEDGER_RESTORE_OPERATION_DEFINITION_ID: operation_module.LedgerRestoreExecutor,
        LEDGER_EXCLUDE_OPERATION_DEFINITION_ID: operation_module.LedgerExcludeExecutor,
    }[operation_id]
    completed = await executor_type(_ports_factory(context)).execute(_request(operation_id), context)

    assert isinstance(completed, str)
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.UPDATED]
    assert len(action_calls) == 1
    assert action_calls[0]["transaction_id"] == _TRANSACTION_ID
    assert action_calls[0]["reason"] == "test reason"
    assert action_calls[0]["actor"] == "operator"
    assert action_calls[0]["source_command"] == f"aeat app {operation_id.replace('.', ' ')}"
    assert len(stored) == 1
    assert stored[0].result.result == _projection(operation_id)


@pytest.mark.asyncio
async def test_prewrite_finalized_blocker_refusal_preserves_typed_recovery_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = LEDGER_ARCHIVE_OPERATION_DEFINITION_ID
    effects: list[OperationEffect] = []
    stored: list[LedgerLifecycleExecutionResult] = []
    context = _context(effects, operation_id=operation_id, stored=stored)
    blocker_context = {
        "transaction_ids": _TRANSACTION_ID + "," + ("b" * 64),
        "work_unit_id": "c" * 64,
        "calculation_revision_id": "d" * 64,
        "modelo": "303",
        "filing_year": "2026",
        "period": "1T",
        "blocking_reference_count": "2",
    }

    def blocked(**_kwargs: object) -> object:
        raise TransactionValidationError(
            "archive refused because a finalized revision cites the row", context=blocker_context
        )

    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, "archive_manual_transaction", blocked)
    executor = operation_module.LedgerArchiveExecutor(_ports_factory(context))

    completed = await executor.execute(_request(operation_id), context)

    assert isinstance(completed, OperationRefusalEvidence)
    assert completed.refusal_code == LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE
    assert completed.detail_ref == "d" * 64
    assert effects == [OperationEffect.UNKNOWN, OperationEffect.NONE]
    refusal = stored[0].result
    assert refusal.outcome == "validation_error"
    assert refusal.validation is not None
    assert refusal.validation.transaction_id == _TRANSACTION_ID
    assert refusal.validation.transaction_ids == (_TRANSACTION_ID, "b" * 64)
    assert refusal.validation.blocking_reference is not None
    assert refusal.validation.blocking_reference.work_unit_id == "c" * 64
    assert refusal.validation.blocking_reference.calculation_revision_id == "d" * 64
    assert refusal.validation.blocking_reference.revision_state is None
    assert refusal.validation.blocking_reference_count == 2


@pytest.mark.asyncio
async def test_validation_exception_after_writer_entry_remains_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = LEDGER_ARCHIVE_OPERATION_DEFINITION_ID
    effects: list[OperationEffect] = []
    stored: list[LedgerLifecycleExecutionResult] = []
    context = _context(effects, operation_id=operation_id, stored=stored)

    def uncertain(**kwargs: object) -> object:
        ports = cast(LedgerActionPorts, kwargs["ports"])
        ports.transaction_repository.save_with_secure_object_writes(
            cast(TransactionCatalogue, object()),
            (),
        )
        raise TransactionValidationError("writer reported uncertain outcome")

    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", lambda _prefix, _ids: _TRANSACTION_ID)
    monkeypatch.setattr(operation_module, "archive_manual_transaction", uncertain)
    executor = operation_module.LedgerArchiveExecutor(_ports_factory(context))

    with pytest.raises(TransactionValidationError, match="uncertain outcome"):
        await executor.execute(_request(operation_id), context)

    assert effects == [OperationEffect.UNKNOWN]
    assert stored == []


@pytest.mark.asyncio
async def test_prefix_refusal_happens_before_commit_and_publishes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operation_id = LEDGER_ARCHIVE_OPERATION_DEFINITION_ID
    effects: list[OperationEffect] = []
    stored: list[LedgerLifecycleExecutionResult] = []
    context = _context(effects, operation_id=operation_id, stored=stored)

    def ambiguous(_prefix: str, _ids: object) -> str:
        raise TransactionIdPrefixError("transaction prefix is ambiguous")

    monkeypatch.setattr(operation_module, "require_active_bucket_id", lambda: str(_PROFILE))
    monkeypatch.setattr(operation_module, "resolve_transaction_id", ambiguous)
    executor = operation_module.LedgerArchiveExecutor(_ports_factory(context))

    completed = await executor.execute(_request(operation_id), context)

    assert isinstance(completed, OperationRefusalEvidence)
    assert completed.refusal_code == LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE
    assert effects == [OperationEffect.NONE]
    refusal = stored[0].result
    assert refusal.validation is not None
    assert refusal.validation.transaction_id is None
    assert refusal.validation.blocking_reference is None


def test_request_is_closed_and_refusal_projection_requires_complete_blocker_facts() -> None:
    request = LedgerLifecycleMutationRequest(
        profile_id=_PROFILE,
        transaction_id=_TRANSACTION_ID[:12],
        actor="operator",
        reason="change",
    )
    assert LedgerLifecycleMutationRequest.model_validate_json(request.model_dump_json()) == request
    with pytest.raises(ValidationError):
        LedgerLifecycleMutationRequest.model_validate({**request.model_dump(), "unexpected": "value"})
    with pytest.raises(ValidationError):
        LedgerLifecycleValidationProjection(
            messages=("finalized revision blocks this action",),
            blocking_reference_count=1,
        )


def test_terminal_projector_binds_exact_success_and_refusal_receipts() -> None:
    operation_id = LEDGER_ARCHIVE_OPERATION_DEFINITION_ID
    success = LedgerLifecycleExecutionResult(
        result=LedgerLifecycleOperationResult(
            outcome="updated",
            profile_id=_PROFILE,
            operation_id=operation_id,
            result=_projection(operation_id),
        ),
    )
    refused = LedgerLifecycleExecutionResult(
        result=LedgerLifecycleOperationResult(
            outcome="validation_error",
            profile_id=_PROFILE,
            operation_id=operation_id,
            validation=LedgerLifecycleValidationProjection(messages=("already archived",)),
        ),
    )

    def receipt(condition: OperationTerminalCondition, effect: OperationEffect) -> OperationTerminalReceipt:
        is_refused = condition is OperationTerminalCondition.REFUSED
        return OperationTerminalReceipt(
            identity=OperationIdentity(
                operation_id="f" * 64,
                definition_id=operation_id,
                subject_ref=profile_operation_subject(str(_PROFILE)),
            ),
            revision=1,
            condition=condition,
            effect=effect,
            settled_at=_AT,
            result_ref=None if is_refused else "a" * 64,
            refusal_ref=LEDGER_LIFECYCLE_VALIDATION_REFUSAL_CODE if is_refused else None,
            refusal_detail_ref="b" * 64 if is_refused else None,
        )

    assert (
        operation_module._project_result(
            success,
            receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.UPDATED),
        )
        == success.result
    )
    assert (
        operation_module._project_result(
            refused,
            receipt(OperationTerminalCondition.REFUSED, OperationEffect.NONE),
        )
        == refused.result
    )
    with pytest.raises(ValueError):
        operation_module._project_result(
            success,
            receipt(OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE),
        )
