"""The batch edit preview writes nothing and the write happens only for the reviewed plan."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ....core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.spending_category_catalogue import spending_category_tokens
from ....domain.transactions.models import Transaction
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.refusal_evidence import OperationRefusalEvidence
from ...operations.registry_schema_validation import strict_model_json_schema
from .. import batch_update_operation as batch_operation
from ..batch_update_contracts import (
    LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID,
    LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE,
    LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID,
    LedgerBatchUpdateExecutionResult,
    LedgerBatchUpdatePreviewRequest,
    LedgerBatchUpdateRequest,
    LedgerBatchUpdateRow,
    LedgerPropertySet,
)
from .bulk_classify_operation_support import PROFILE_ID, BulkClassifySubject
from .test_classification_rule_plan import transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


@pytest.fixture
def transactions() -> tuple[Transaction, Transaction]:
    return (
        transaction(provider_id="batch-one", description="Synthetic batch one"),
        transaction(provider_id="batch-two", description="Synthetic batch two"),
    )


def _subject(
    monkeypatch: pytest.MonkeyPatch,
    authority: PinnedAuthorityOperation,
    transactions: tuple[Transaction, ...],
) -> BulkClassifySubject:
    monkeypatch.setattr(
        "cadrumo.application.operations.profile_guard.require_active_bucket_id", lambda: str(PROFILE_ID)
    )
    return BulkClassifySubject(operation=authority, transactions=transactions)


def _context(subject: BulkClassifySubject, definition_id: str) -> OperationExecutorContext:
    return cast(
        OperationExecutorContext,
        SimpleNamespace(
            identity=SimpleNamespace(
                definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID))
            ),
            authority_operation=subject.operation,
            cancellation=subject.fence,
            events=subject.events,
            operands=subject.operands,
        ),
    )


def _rows(
    authority: PinnedAuthorityOperation, transactions: tuple[Transaction, ...]
) -> tuple[LedgerBatchUpdateRow, ...]:
    category = spending_category_tokens(authority=authority)[0].value
    properties = LedgerPropertySet(
        fields=("business_classification", "category_id"), business_classification="BUSINESS", category_id=category
    )
    return tuple(
        LedgerBatchUpdateRow(
            transaction_id=row.transaction_id, expected_modified_at=row.modified_at.isoformat(), properties=properties
        )
        for row in transactions
    )


def _preview(rows: tuple[LedgerBatchUpdateRow, ...]) -> OperationRequest[LedgerBatchUpdatePreviewRequest]:
    return OperationRequest[LedgerBatchUpdatePreviewRequest](
        definition_id=LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=LedgerBatchUpdatePreviewRequest(profile_id=PROFILE_ID, rows=rows),
    )


def _apply(rows: tuple[LedgerBatchUpdateRow, ...], digest: str) -> OperationRequest[LedgerBatchUpdateRequest]:
    return OperationRequest[LedgerBatchUpdateRequest](
        definition_id=LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=LedgerBatchUpdateRequest(profile_id=PROFILE_ID, rows=rows, reviewed_plan_digest=digest),
    )


def _receipt(
    definition_id: str, condition: OperationTerminalCondition, effect: OperationEffect
) -> OperationTerminalReceipt:
    refused = condition is OperationTerminalCondition.REFUSED
    return OperationTerminalReceipt(
        identity=OperationIdentity(
            operation_id="a" * 64, definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID))
        ),
        revision=1,
        settled_at=datetime(2026, 5, 1, tzinfo=UTC),
        condition=condition,
        effect=effect,
        result_ref=None if refused else "d" * 64,
        refusal_ref=LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE if refused else None,
        refusal_detail_ref="d" * 64 if refused else None,
    )


def _previewed_digest(subject: BulkClassifySubject, rows: tuple[LedgerBatchUpdateRow, ...]) -> str:
    executor = batch_operation.LedgerBatchUpdatePreviewExecutor(subject.compose)
    asyncio.run(
        executor.execute(_preview(rows), _context(subject, LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID))
    )
    return cast(LedgerBatchUpdateExecutionResult, subject.operands.values[-1]).result.plan_digest


def test_requests_are_strict_and_name_each_movement_once(
    authority_operation: PinnedAuthorityOperation, transactions: tuple[Transaction, Transaction]
) -> None:
    rows = _rows(authority_operation, transactions)
    for model in (LedgerBatchUpdatePreviewRequest, LedgerBatchUpdateRequest, LedgerBatchUpdateExecutionResult):
        strict_model_json_schema(model)
    with pytest.raises(ValidationError):
        LedgerBatchUpdatePreviewRequest(profile_id=PROFILE_ID, rows=(rows[0], rows[0]))
    with pytest.raises(ValidationError):
        LedgerPropertySet(fields=("notes",), category_id="unselected")
    with pytest.raises(ValidationError):
        LedgerBatchUpdateRow(
            transaction_id="x", expected_modified_at="2026-05-01T00:00:00", properties=rows[0].properties
        )


def test_preview_plans_every_row_and_writes_nothing(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    transactions: tuple[Transaction, Transaction],
) -> None:
    subject = _subject(monkeypatch, authority_operation, transactions)
    _previewed_digest(subject, _rows(authority_operation, transactions))
    execution = cast(LedgerBatchUpdateExecutionResult, subject.operands.values[-1])
    assert execution.result.outcome == "previewed"
    assert execution.result.counts.applied == 2
    assert subject.repository.write_attempts == 0 and subject.fence.entries == 0
    assert subject.events.effects == [OperationEffect.NONE]
    receipt = _receipt(
        LEDGER_BATCH_UPDATE_PREVIEW_OPERATION_DEFINITION_ID, OperationTerminalCondition.SUCCEEDED, OperationEffect.NONE
    )
    assert batch_operation.project_batch_update_preview_result(execution, receipt) == execution.result
    with pytest.raises(ValueError):
        batch_operation.project_batch_update_preview_result(
            execution, receipt.model_copy(update={"effect": OperationEffect.UPDATED})
        )


def test_apply_writes_the_reviewed_plan_once_and_a_replay_writes_nothing_more(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    transactions: tuple[Transaction, Transaction],
) -> None:
    rows = _rows(authority_operation, transactions)
    subject = _subject(monkeypatch, authority_operation, transactions)
    digest = _previewed_digest(subject, rows)
    executor = batch_operation.LedgerBatchUpdateExecutor(subject.compose)
    asyncio.run(executor.execute(_apply(rows, digest), _context(subject, LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID)))
    applied = cast(LedgerBatchUpdateExecutionResult, subject.operands.values[-1]).result
    assert applied.outcome == "applied" and applied.counts.applied == 2 and applied.bucket_event_ids
    assert subject.repository.committed_writes == 1 and subject.fence.entries == 1
    assert subject.events.effects[-1] is OperationEffect.UPDATED

    # The same request again finds its rows changed since they were seen and writes nothing.
    replay = asyncio.run(
        executor.execute(_apply(rows, digest), _context(subject, LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID))
    )
    assert isinstance(replay, OperationRefusalEvidence)
    assert replay.refusal_code == LEDGER_BATCH_UPDATE_PLAN_CHANGED_REFUSAL_CODE
    assert subject.repository.committed_writes == 1
    changed = cast(LedgerBatchUpdateExecutionResult, subject.operands.values[-1]).result
    assert changed.outcome == "plan_changed" and changed.counts.conflict == 2


def test_apply_with_another_digest_refuses_and_carries_the_plan_it_found(
    monkeypatch: pytest.MonkeyPatch,
    authority_operation: PinnedAuthorityOperation,
    transactions: tuple[Transaction, Transaction],
) -> None:
    subject = _subject(monkeypatch, authority_operation, transactions)
    executor = batch_operation.LedgerBatchUpdateExecutor(subject.compose)
    refused = asyncio.run(
        executor.execute(
            _apply(_rows(authority_operation, transactions), "0" * 64),
            _context(subject, LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID),
        )
    )
    assert isinstance(refused, OperationRefusalEvidence)
    assert subject.repository.write_attempts == 0 and subject.fence.entries == 0
    assert subject.events.effects == [OperationEffect.NONE]
    execution = cast(LedgerBatchUpdateExecutionResult, subject.operands.values[-1])
    assert execution.result.outcome == "plan_changed" and execution.result.counts.applied == 2
    receipt = _receipt(
        LEDGER_BATCH_UPDATE_OPERATION_DEFINITION_ID, OperationTerminalCondition.REFUSED, OperationEffect.NONE
    )
    assert batch_operation.project_batch_update_result(execution, receipt) == execution.result
    with pytest.raises(ValueError):
        batch_operation.project_batch_update_result(
            execution,
            receipt.model_copy(
                update={
                    "identity": receipt.identity.model_copy(
                        update={"subject_ref": profile_operation_subject(str(uuid4()))}
                    )
                }
            ),
        )
