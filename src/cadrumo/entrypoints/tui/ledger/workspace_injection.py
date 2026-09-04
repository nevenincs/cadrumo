"""The dependency set one Ledger workspace is constructed from.

The route factory and the workspace controller each declared these eleven
parameters in full, so adding a twelfth meant editing both signatures and the
forwarding call between them. Declaring them once removes that, and makes the
set itself nameable: a caller now hands over ONE thing whose contents are
validated at construction rather than eleven arguments validated in two places.

The guard runs in ``__post_init__``, which is what closes the gap the two
signatures allowed. Previously the factory refused a miswired ``review_action``
and the controller did not, so a caller constructing the controller directly
skipped that refusal. There is one construction path now, so a check cannot
apply on one and not the other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ....application.ledger.attachment_review import AttachmentReviewItem
from ....application.operator_actions.models import ActionReference
from ....core.identity import TransactionId
from .action_guards import require_canonical_ledger_actions
from .models import (
    LedgerClassificationSubmitterV1,
    LedgerImportSubmitterV1,
    LedgerLinkSubmitterV1,
    LedgerPreparedImportV1,
)


@dataclass(frozen=True, slots=True)
class LedgerWorkspaceInjection:
    """Every dependency the Ledger workspace is given from outside.

    An absent action means the area is not offered, which is distinct from an
    action that is offered but miswired: the first is a supported state, the
    second is refused at construction.
    """

    review_action: ActionReference
    classify_action: ActionReference | None = None
    classification_target: TransactionId | None = None
    classification_submitter: LedgerClassificationSubmitterV1 | None = None
    prepared_imports: tuple[LedgerPreparedImportV1, ...] = ()
    import_submitter: LedgerImportSubmitterV1 | None = None
    evidence_action: ActionReference | None = None
    evidence_items: tuple[AttachmentReviewItem, ...] | None = None
    link_action: ActionReference | None = None
    link_submitter: LedgerLinkSubmitterV1 | None = None

    def __post_init__(self) -> None:
        """Refuse a miswired action or a duplicated prepared-import identity."""
        require_canonical_ledger_actions(
            review_action=self.review_action,
            classify_action=self.classify_action,
            evidence_action=self.evidence_action,
            link_action=self.link_action,
        )
        choice_ids = tuple(choice.choice_id for choice in self.prepared_imports)
        if len(choice_ids) != len(set(choice_ids)):
            raise ValueError("prepared import choice identities must be unique")


__all__ = ["LedgerWorkspaceInjection"]
