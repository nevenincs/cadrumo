"""Synthetic ledger rows for conformance scenarios, seeded through the production repositories."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from ...application.ledger.action_ports import LedgerActionPorts
from ...application.ledger.actions_manual import create_manual_transaction
from ...application.ledger.models import ManualLedgerTransactionCommand
from ...core.time.clock import now
from ...domain.transactions.enums import BusinessClassification, TransactionDirection
from ..ledger_action_composition import compose_ledger_action_ports
from .conformance_family_contract import ConformanceFamilyContext, ConformanceOutcome

SEED_ACTOR = "registered-executor-conformance"


def ledger_action_ports(context: ConformanceFamilyContext) -> LedgerActionPorts:
    """Compose the production ledger persistence for the enrolled profile and its pinned authority."""
    return compose_ledger_action_ports(bucket_id=str(context.profile_id), operation=context.operation)


def seed_manual_transaction(
    context: ConformanceFamilyContext,
    *,
    booked_date: date,
    amount: Decimal,
    description: str,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> str:
    """Persist one manual ledger row through the production writer and return its transaction id."""
    created = create_manual_transaction(
        ManualLedgerTransactionCommand(
            bucket_id=str(context.profile_id),
            booked_date=booked_date,
            amount=amount,
            direction=direction,
            description=description,
            business_classification=business_classification,
            actor=SEED_ACTOR,
        ),
        ports=ledger_action_ports(context),
        occurred_at=now(),
    )
    return created.ref.transaction_id


def ledger_unchanged_verifier(context: ConformanceFamilyContext) -> Callable[[ConformanceOutcome], None]:
    """Capture the ledger now and return the check that a refused operation left it untouched."""
    before = ledger_action_ports(context)
    transactions_before = before.transaction_repository.load()
    events_before = before.bucket_event_repository.load()

    def verify(outcome: ConformanceOutcome) -> None:
        del outcome
        after = ledger_action_ports(context)
        assert after.transaction_repository.load() == transactions_before
        assert after.bucket_event_repository.load() == events_before

    return verify
