"""Registered-executor conformance scenario for the automation-facing typed ledger history."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ...application.ledger.history_operation import (
    LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,
    LedgerHistoryRequest,
    LedgerHistoryTypedProjection,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...domain.buckets.event import BucketEventObjectType
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .conformance_ledger_seed_support import SEED_ACTOR, ledger_action_ports, seed_manual_transaction

_SEED_DESCRIPTION = "conformance typed history seed"


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    profile_id = context.profile_id
    transaction_id = seed_manual_transaction(
        context, booked_date=date(2025, 1, 15), amount=Decimal("12.00"), description=_SEED_DESCRIPTION
    )
    # The production writer's own stored events are the expectation: every
    # entry it wrote must be one the typed result declares.
    stored = (
        ledger_action_ports(context)
        .bucket_event_repository.load()
        .for_object(object_type=BucketEventObjectType.LEDGER_TRANSACTION, object_id=transaction_id)
    )
    assert stored

    def verify(outcome: ConformanceOutcome) -> None:
        history = outcome.resolve_result(LedgerHistoryTypedProjection)
        assert history.profile_id == profile_id
        assert history.transaction_id == transaction_id
        assert history.object_ids == (transaction_id,)
        assert history.event_count == len(stored)
        assert [event.event_id for event in history.events] == [event.event_id for event in stored]
        for released, event in zip(history.events, stored, strict=True):
            assert (released.event_type, released.occurred_at) == (event.event_type, event.occurred_at)
            assert (released.actor, released.object_id) == (SEED_ACTOR, transaction_id)
            assert released.details.model_dump(exclude_none=True) == dict(event.payload)
            assert released.undeclared_detail_count == 0
            assert not released.model_reason_withheld and not released.output_path_withheld

    return ConformancePreparation(
        subject_ref=profile_operation_subject(str(profile_id)),
        request=LedgerHistoryRequest(profile_id=profile_id, transaction_prefix=transaction_id[:12]),
        verify=verify,
    )


LEDGER_HISTORY_TYPED_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        # A single-phase read that publishes its own id and settles NONE
        # (application/ledger/history_operation.py LedgerHistoryTypedExecutor).
        RegisteredExecutorConformanceCase(
            LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.NONE,
            (LEDGER_HISTORY_TYPED_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
