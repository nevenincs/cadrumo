"""The dependency set one Ledger workspace is constructed from.

The route factory and the workspace controller each declared these
parameters in full, so adding one more meant editing both signatures and the
forwarding call between them. Declaring them once removes that, and makes the
set itself nameable: a caller now hands over ONE thing whose contents are
validated at construction rather than a dozen arguments validated in two places.

The guard runs in ``__post_init__``, which is what closes the gap the two
signatures allowed. Previously the factory refused a miswired ``review_action``
and the controller did not, so a caller constructing the controller directly
skipped that refusal. There is one construction path now, so a check cannot
apply on one and not the other.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.ledger.workspace import LedgerWorkspaceProjectionV1
from ....application.operator_actions.models import ActionReference
from .action_guards import require_canonical_ledger_actions
from .models import (
    LedgerClassificationSubmitterV1,
    LedgerEvidenceDoorV1,
    LedgerImportDoorV1,
    LedgerInvoiceAddDoorV1,
    LedgerLinkSubmitterV1,
)


@dataclass(frozen=True, slots=True)
class LedgerWorkspaceRefreshV1:
    """The per-visit state a workspace re-reads after it has written something."""

    projection: LedgerWorkspaceProjectionV1
    evidence_items: tuple[AttachmentReviewItem, ...] | None


type LedgerWorkspaceRefreshDoorV1 = Callable[[], LedgerWorkspaceRefreshV1]


@dataclass(frozen=True, slots=True)
class LedgerWorkspaceInjection:
    """Every dependency the Ledger workspace is given from outside.

    An absent action means the area is not offered, which is distinct from an
    action that is offered but miswired: the first is a supported state, the
    second is refused at construction.
    """

    review_action: ActionReference
    classify_action: ActionReference | None = None
    classification_submitter: LedgerClassificationSubmitterV1 | None = None
    import_door: LedgerImportDoorV1 | None = None
    evidence_action: ActionReference | None = None
    evidence_items: tuple[AttachmentReviewItem, ...] | None = None
    link_action: ActionReference | None = None
    link_submitter: LedgerLinkSubmitterV1 | None = None
    invoice_add_door: LedgerInvoiceAddDoorV1 | None = None
    evidence_door: LedgerEvidenceDoorV1 | None = None
    refresh: LedgerWorkspaceRefreshDoorV1 | None = None
    """Re-read the projection after a write; without it a flow shows its own result only."""

    def __post_init__(self) -> None:
        """Refuse a miswired action."""
        require_canonical_ledger_actions(
            review_action=self.review_action,
            classify_action=self.classify_action,
            evidence_action=self.evidence_action,
            link_action=self.link_action,
        )


__all__ = ["LedgerWorkspaceInjection", "LedgerWorkspaceRefreshDoorV1", "LedgerWorkspaceRefreshV1"]
