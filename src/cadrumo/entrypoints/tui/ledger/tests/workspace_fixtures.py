"""Synthetic ledger-workspace projections, contexts, and actions for tests.

The ledger screens are exercised from this package and, at the whole-TUI
level, from ``entrypoints.tui.tests``. The fixtures live here, beside the
screens they describe, so every suite builds the same projection instead of
reaching into another suite's module internals.
"""

from __future__ import annotations

from typing import cast

from .....application.ledger.workspace import (
    LedgerWorkspaceArea,
    LedgerWorkspaceAreaStateV1,
    LedgerWorkspaceAvailability,
    LedgerWorkspaceEntryRefV1,
    LedgerWorkspaceProjectionV1,
    LedgerWorkspaceSource,
    LedgerWorkspaceStatus,
)
from .....application.operator_actions.catalogue import lookup_action
from .....application.operator_actions.models import ActionReference
from .....core.identity.transaction_ids import TransactionId
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..controller import LedgerWorkspaceController
from ..workspace_injection import LedgerWorkspaceInjection

#: The two synthetic transactions every ledger fixture projection carries.
LEDGER_TX_A = cast("TransactionId", "a" * 64)
LEDGER_TX_B = cast("TransactionId", "b" * 64)


def ledger_projection(*, unavailable: LedgerWorkspaceArea | None = None) -> LedgerWorkspaceProjectionV1:
    """Build a two-entry workspace projection, optionally locking one area."""
    states = []
    counts = {
        LedgerWorkspaceArea.OVERVIEW: 3,
        LedgerWorkspaceArea.ENTRIES: 2,
        LedgerWorkspaceArea.REVIEW: 2,
        LedgerWorkspaceArea.IMPORT: 0,
        LedgerWorkspaceArea.CLASSIFICATION: 2,
        LedgerWorkspaceArea.EVIDENCE: 0,
        LedgerWorkspaceArea.RECONCILIATION: 0,
    }
    for area in LedgerWorkspaceArea:
        blocked = area is unavailable
        states.append(
            LedgerWorkspaceAreaStateV1(
                area=area,
                sources=(LedgerWorkspaceSource.LOCAL_LEDGER,),
                availability=LedgerWorkspaceAvailability.LOCKED if blocked else LedgerWorkspaceAvailability.AVAILABLE,
                reason_code="ledger.locked" if blocked else None,
                status=(
                    LedgerWorkspaceStatus.UNMEASURED
                    if area in {LedgerWorkspaceArea.IMPORT, LedgerWorkspaceArea.EVIDENCE}
                    else LedgerWorkspaceStatus.NEEDS_ATTENTION
                ),
                item_count=counts[area],
            )
        )
    entries = (
        LedgerWorkspaceEntryRefV1(
            transaction_id=LEDGER_TX_A,
            review_status="pending",
            date="2026-03-14",
            amount="1250.00",
            currency="EUR",
            direction="outgoing",
            counterparty="Suministros Delta SL",
            description="Material de oficina",
            business_classification="business",
        ),
        LedgerWorkspaceEntryRefV1(
            transaction_id=LEDGER_TX_B,
            review_status="reviewed",
            date="2026-03-02",
            amount="480.50",
            currency="EUR",
            direction="incoming",
            counterparty="Cliente Omega SA",
            description="Servicios de consultoría",
            business_classification="business",
        ),
    )
    return LedgerWorkspaceProjectionV1(
        bucket_id="synthetic-bucket",
        areas=tuple(states),
        entries=entries,
        review_transaction_ids=(LEDGER_TX_A, LEDGER_TX_B),
        invoice_reconciliations=(),
        link_inconsistencies=(),
        affected_declarations=(),
    )


def ledger_context() -> TuiScreenContextV1:
    """The plain ledger workspace context, with nothing focused."""
    return TuiScreenContextV1(destination="workbench.ledger")


def ledger_focused_context(transaction_id: TransactionId) -> TuiScreenContextV1:
    """A workspace context already addressed at one entry.

    Selection lives in ``context.focus``, so a test that needs the operator to
    have chosen a row states it here rather than injecting a target. That is
    the same channel the production selection handler writes.
    """
    return TuiScreenContextV1(
        destination="workbench.ledger",
        focus=TuiFocusIdentityV1(
            destination="workbench.ledger",
            semantic_key="ledger.transaction",
            restore_token=transaction_id,
        ),
    )


def ledger_review_action() -> ActionReference:
    """The canonical ledger review action reference."""
    declaration = lookup_action("operator.ledger.review")
    return ActionReference(action_id=declaration.action_id)


def ledger_evidence_action() -> ActionReference:
    """The canonical ledger evidence-review action reference."""
    return ActionReference(action_id=lookup_action("operator.ledger.evidence.review.list").action_id)


def ledger_controller(
    projection: LedgerWorkspaceProjectionV1,
    context: TuiScreenContextV1 | None = None,
) -> LedgerWorkspaceController:
    """Build a ledger workspace controller over *projection*."""
    return LedgerWorkspaceController(
        context or ledger_context(), projection, LedgerWorkspaceInjection(review_action=ledger_review_action())
    )
