"""Synthetic ledger-workspace projections, contexts, and actions for tests.

The ledger screens are exercised from this package and, at the whole-TUI
level, from ``entrypoints.tui.tests``. The fixtures live here, beside the
screens they describe, so every suite builds the same projection instead of
reaching into another suite's module internals.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from .....application.ledger.models import ManualLedgerTransactionResult
from .....application.ledger.workspace import (
    LedgerAffectedDeclarationRefV1,
    LedgerInvoiceReconciliationRefV1,
    LedgerLinkInconsistencyRefV1,
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
from .....core.period import Period
from .....domain.transactions.models import BucketTransactionRef
from ...components.host import ScreenHostApp
from ...navigation import TuiFocusIdentityV1, TuiScreenContextV1
from ..controller import LedgerWorkspaceController
from ..models import LedgerClassificationSubmissionV1
from ..workspace_injection import LedgerWorkspaceInjection
from .review_door_fixtures import MemoryLedgerReviewDoor, projection_review_rows

if TYPE_CHECKING:
    from textual.screen import Screen

#: The two synthetic transactions every ledger fixture projection carries.
LEDGER_TX_A = cast("TransactionId", "a" * 64)
LEDGER_TX_B = cast("TransactionId", "b" * 64)
#: The invoice the reconciled fixture projection suggests for ``LEDGER_TX_A``.
LEDGER_SUGGESTED_INVOICE = "c" * 64


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


def ledger_review_door(projection: LedgerWorkspaceProjectionV1) -> MemoryLedgerReviewDoor:
    """A review door answering the queue *projection*'s own review identities describe."""
    return MemoryLedgerReviewDoor(projection_review_rows(projection))


def ledger_controller(
    projection: LedgerWorkspaceProjectionV1,
    context: TuiScreenContextV1 | None = None,
) -> LedgerWorkspaceController:
    """Build a ledger workspace controller over *projection*, its review queue read through a door."""
    return LedgerWorkspaceController(
        context or ledger_context(),
        projection,
        LedgerWorkspaceInjection(review_action=ledger_review_action(), review_door=ledger_review_door(projection)),
    )


def ledger_reconciled_projection() -> LedgerWorkspaceProjectionV1:
    """The fixture projection with one link suggestion, one inconsistency and one affected declaration."""
    return ledger_projection().model_copy(
        update={
            "invoice_reconciliations": (
                LedgerInvoiceReconciliationRefV1(
                    invoice_id=LEDGER_SUGGESTED_INVOICE,
                    transaction_id=LEDGER_TX_A,
                    amount_match=True,
                    counterparty_match=True,
                    score="1.0",
                    invoice_total="1250.00",
                    transaction_amount="1250.00",
                    invoice_counterparty="Suministros Delta SL",
                    transaction_counterparty="Suministros Delta SL",
                ),
            ),
            "link_inconsistencies": (
                LedgerLinkInconsistencyRefV1(invoice_id="f" * 64, transaction_id=LEDGER_TX_A, direction="invoice-only"),
            ),
            "affected_declarations": (
                LedgerAffectedDeclarationRefV1(
                    modelo="303",
                    filing_year=2026,
                    period=Period.from_year_and_code(2026, "2T"),
                    calculation_revision_id="b" * 64,
                    changed_count=2,
                    removed_count=1,
                ),
            ),
        }
    )


def ledger_classify_action() -> ActionReference:
    """The canonical ledger classification action reference."""
    return ActionReference(action_id=lookup_action("operator.ledger.classify").action_id)


class ClassificationDoor:
    """A classification writer that records every submission and answers it as written."""

    def __init__(self) -> None:
        self.calls: list[LedgerClassificationSubmissionV1] = []

    async def __call__(self, submission: LedgerClassificationSubmissionV1) -> ManualLedgerTransactionResult:
        self.calls.append(submission)
        return ManualLedgerTransactionResult.model_construct(
            ref=BucketTransactionRef.model_construct(transaction_id=submission.transaction_id),
        )


class WorkspaceHostApp(ScreenHostApp[None]):
    """A host that replaces a workspace body the way the production root does.

    The deferral is the point.  Textual dispatches a screen's result callback
    through whichever message pump was active when that screen was pushed, so
    pushing a replacement from inside the outgoing screen's own handler
    registers the return journey against a pump that is about to stop.  The
    root defers the swap onto its own pump for exactly that reason, and a host
    that pushed directly would pass a journey test while production stranded
    the operator.  Mirroring the deferral keeps the proof honest.
    """

    def replace_workspace_body(self, screen: Screen[None], /) -> None:
        """Defer the swap onto this host's pump, as the root shell does."""
        self.call_next(self._replace_workspace_body, screen)

    def _replace_workspace_body(self, screen: Screen[None]) -> None:
        """Discard the outgoing body before mounting exactly one replacement."""
        while len(self.screen_stack) > 1:
            self.pop_screen()
        self.push_screen(screen, self.exit)
