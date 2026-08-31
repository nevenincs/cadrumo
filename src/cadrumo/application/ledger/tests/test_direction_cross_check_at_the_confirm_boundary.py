"""The document's suggested direction is compared against the operator's stated one.

The reading stage asks which party's block prints the filer's own identifier and
stamps the answer as a suggestion; the operator states the direction on the
confirm verb. Neither stage holds both, so the comparison lives at the confirm
boundary -- and until it did, the ``suggested_kind`` slot was written on every
read and consumed by nothing.

Direction is not cosmetic. It decides which informativa the record feeds and on
which side, and AEAT reconciles the two counterparties' declarations against each
other, so a purchase booked as a sale is wrong in a way that reconciles
internally.

The disagreement is stamped as an ordinary
:attr:`~core.DraftDiscrepancyKind.DIRECTION_CONTRADICTED` finding rather than
raised. It therefore becomes a per-document blocker the operator answers with a
stated reason: two honest readings can disagree, and an operator who is right
about a misleading layout must have a way through.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....domain.iva.classification import InvoiceKind
from ..confirmation_gate import ConfirmationBlockedError, confirmation_blockers, resolved_blockers
from ..evidence_draft import InvoiceDraft, _with_direction_contradiction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _draft(suggested: InvoiceKind | None) -> InvoiceDraft:
    return InvoiceDraft(
        supplier_tax_id="B12345674",
        customer_tax_id="B17283946",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        suggested_kind=suggested,
    )


def _kinds(draft: InvoiceDraft) -> set[DraftDiscrepancyKind]:
    return {finding.kind for finding in draft.discrepancies}


def test_a_document_placing_the_filer_on_the_other_side_raises_the_contradiction() -> None:
    """The case the cross-check exists for.

    The document settled ``received`` -- the filer's own identifier is printed
    inside the recipient's block -- and the operator is confirming it as issued.
    """
    stamped = _with_direction_contradiction(_draft(InvoiceKind.RECEIVED), kind=InvoiceKind.ISSUED)

    assert DraftDiscrepancyKind.DIRECTION_CONTRADICTED in _kinds(stamped)


def test_the_contradiction_names_both_directions_so_the_operator_can_judge_it() -> None:
    """A blocker saying only "direction disagrees" cannot be answered.

    The operator has the document; they need to be told what the document was
    read as and what they asked for, in order to decide which is wrong.
    """
    stamped = _with_direction_contradiction(_draft(InvoiceKind.ISSUED), kind=InvoiceKind.RECEIVED)

    detail = next(f.detail for f in stamped.discrepancies if f.kind is DraftDiscrepancyKind.DIRECTION_CONTRADICTED)
    assert InvoiceKind.ISSUED.value in detail
    assert InvoiceKind.RECEIVED.value in detail


def test_an_agreeing_document_raises_nothing() -> None:
    """The bound. Without it the check could be "always contradict"."""
    stamped = _with_direction_contradiction(_draft(InvoiceKind.RECEIVED), kind=InvoiceKind.RECEIVED)

    assert stamped.discrepancies == ()


def test_a_document_that_settled_nothing_raises_nothing() -> None:
    """Declining to answer is not disagreement.

    Most outcomes of the derivation carry no direction -- the filer absent, on
    both sides, or the document stating no usable party partition. Reading any
    of those as a contradiction would block the majority of the corpus on a
    question the document never answered.
    """
    stamped = _with_direction_contradiction(_draft(None), kind=InvoiceKind.ISSUED)

    assert stamped.discrepancies == ()


def test_the_existing_findings_survive_the_stamp() -> None:
    """The stamp appends; it must not replace what the reading stage found."""
    base = _draft(InvoiceKind.RECEIVED)
    with_closure = base.model_copy(
        update={
            "discrepancies": (
                *base.discrepancies,
                *_with_direction_contradiction(base, kind=InvoiceKind.ISSUED).discrepancies,
            ),
        },
    )

    stamped = _with_direction_contradiction(with_closure, kind=InvoiceKind.ISSUED)

    assert len(stamped.discrepancies) == len(with_closure.discrepancies) + 1


def test_the_contradiction_becomes_a_resolvable_blocker_rather_than_a_refusal() -> None:
    """The ruling, exercised: it routes through the ordinary per-finding gate.

    A refusal would leave an operator who is right, facing a document whose
    layout misleads the derivation, with no way through at all.
    """
    stamped = _with_direction_contradiction(_draft(InvoiceKind.RECEIVED), kind=InvoiceKind.ISSUED)

    blockers = confirmation_blockers(stamped)

    assert [blocker.reason for blocker in blockers] == [ConfirmationBlockReason.UNRESOLVED_DIRECTION]
    with pytest.raises(ConfirmationBlockedError):
        resolved_blockers(draft=stamped, resolutions=())
