"""An operator must be able to NAME the reading they chose.

The ambiguity-candidates list exists so an operator holding the document can
decide between two competing readings of one identity. For an identity field
both readings reach them through the redaction funnel as digests -- correctly,
because the value that could not be established is exactly the value that must
not cross an output boundary.

**They could decide and could not say so.** The choose-candidate resolution
matched on the VALUE, which the surface had deliberately withheld, so the only
operator who could express a choice was one who already held the value -- which
is every operator except the ones this surface exists for.

The remedy is the SELECTOR, not the disclosure: a resolution may name its
reading by the digest the surface rendered. That is not a weakening. A digest
matches only a reading the document actually offered, so it is a choice rather
than an assertion -- which is the exact property the refusal message says the
gate enforces, now structurally true instead of true by convention.

The value form stays accepted, for an operator reading it off the document.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import ConfirmationBlockReason, FieldGroundingOutcome, FieldOrigin, FindingResolutionAction
from ....core.redaction import redact_for_cli_output
from ..confirmation_gate import (
    ConfirmationBlockedError,
    FindingResolution,
    confirmation_blockers,
    resolved_blockers,
)
from ..evidence_draft import FieldAmbiguityCandidate, FieldProvenance, InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_FIRST = "B12345674"
_SECOND = "A82645177"


def _ambiguous_draft() -> InvoiceDraft:
    """Return a draft whose supplier identity has two competing readings."""
    return InvoiceDraft(
        taxable_base=Decimal("100.00"),
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.TEXT_LAYER,
                grounding=FieldGroundingOutcome.AMBIGUOUS,
                candidates=(
                    FieldAmbiguityCandidate(value=_FIRST, anchor=_FIRST, note="printed under 'Proveedor'"),
                    FieldAmbiguityCandidate(value=_SECOND, anchor=_SECOND, note="printed under 'Cliente'"),
                ),
                note="two verified identifiers remained and no role evidence picks exactly one",
            ),
        ),
    )


def _only_blocker():
    blockers = confirmation_blockers(_ambiguous_draft())
    assert len(blockers) == 1, "the fixture must raise exactly one blocker"
    assert blockers[0].reason is ConfirmationBlockReason.AMBIGUOUS_IDENTITY
    return blockers[0]


def _resolve_with(token: str) -> None:
    resolved_blockers(
        draft=_ambiguous_draft(),
        resolutions=(
            FindingResolution(
                blocker_id=_only_blocker().blocker_id,
                action=FindingResolutionAction.CHOOSE_CANDIDATE,
                value=token,
            ),
        ),
    )


def test_the_digest_the_surface_rendered_names_the_reading() -> None:
    """The case the row exists for, on the form the operator actually saw."""
    _resolve_with(redact_for_cli_output(_FIRST))


def test_either_competing_reading_can_be_named_by_its_digest() -> None:
    """Both rows must be selectable, or the surface still cannot adjudicate."""
    _resolve_with(redact_for_cli_output(_SECOND))


def test_the_value_still_names_the_reading() -> None:
    """The operator reading off the document is not disenfranchised by the fix."""
    _resolve_with(_FIRST)


def test_a_digest_of_a_reading_the_document_never_offered_is_refused() -> None:
    """The case that proves the gate is still a gate.

    A well-formed digest of some other identity is exactly the shape a
    digest-accepting check could wave through, and it is an assertion rather
    than a choice: the document never offered that reading.
    """
    with pytest.raises(ConfirmationBlockedError):
        _resolve_with(redact_for_cli_output("X1234567L"))


def test_a_value_the_document_never_offered_is_still_refused() -> None:
    """The pre-existing guarantee, unchanged by admitting the second form."""
    with pytest.raises(ConfirmationBlockedError):
        _resolve_with("X1234567L")


def test_the_refusal_names_the_digests_rather_than_the_values() -> None:
    """A refusal must not print the identity the blocker exists to protect.

    It also has to be checkable: the operator compares what they typed against
    what they were shown, and they were shown digests.
    """
    with pytest.raises(ConfirmationBlockedError) as raised:
        _resolve_with("X1234567L")

    # The digests ride on the refusal's facts rather than in an authored
    # sentence, so the confidentiality property is asserted over everything the
    # refusal carries: the facts AND the exception's own text.
    context = raised.value.context or {}
    carried = f"{context}{raised.value}"
    assert redact_for_cli_output(_FIRST) in carried
    assert _FIRST not in carried, "the refusal carried a competing identity in the clear"
    assert _SECOND not in carried


def test_the_candidate_note_is_what_lets_the_operator_decide() -> None:
    """The load-bearing dependency of this whole ruling, guarded HERE.

    Two digests are selectable but not adjudicable on their own. What tells the
    operator WHICH reading is right is the candidate's note -- where on the page
    it was printed -- and that note survives the funnel because it carries no
    identity.

    Asserted in the surface that owns the capability, not only in the funnel
    that could break it. If redaction ever widens to eat this text, adjudication
    stops working with no error and no refusal, and a dependency guarded only at
    the far end is guarded by somebody else's discipline.
    """
    notes = [candidate.note for candidate in _only_blocker().candidates]

    assert notes == ["printed under 'Proveedor'", "printed under 'Cliente'"]
    for note in notes:
        assert redact_for_cli_output(note) == note, "the funnel now redacts the discriminator"


def test_the_two_candidates_do_not_render_to_the_same_digest() -> None:
    """Selectability requires the rendered forms to differ.

    A collision would make the two rows indistinguishable AND make either token
    select ambiguously. Cheap to assert and silent if it ever stopped holding.
    """
    blocker = _only_blocker()

    assert len(set(blocker.candidate_digests)) == len(blocker.candidates)
