"""Blocking findings block: nothing is confirmed blind, and there is no bulk flag.

One refusal test per blocking finding class, each paired with the positive
control the refusal is meaningless without --- a draft raising no finding must
confirm cleanly, or "refuses" is satisfiable by a gate that refuses always.

The completeness of the blocking set is asserted against the enum rather than
against a hand-listed expectation: a check that shipped a new
:class:`~core.DraftDiscrepancyKind` without deciding whether it blocks would
otherwise pass here while silently not blocking in production.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core import (
    ConfirmationBlockReason,
    DraftDiscrepancyKind,
    FieldGroundingOutcome,
    FieldOrigin,
    FindingResolutionAction,
)
from ..confirmation_gate import (
    BLOCKING_REASON_BY_DISCREPANCY_KIND,
    ConfirmationBlockedError,
    FindingResolution,
    confirmation_blockers,
    resolved_blockers,
)
from ..evidence_draft import (
    DraftDiscrepancyFinding,
    FieldAmbiguityCandidate,
    FieldProvenance,
    InvoiceDraft,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _clean_draft() -> InvoiceDraft:
    """A draft that closes arithmetically and names one unambiguous party.

    The positive control for every refusal below. Its figures close exactly
    (100,00 + 21,00 = 121,00) and its single identity envelope is anchored, so
    nothing here can block --- which is what makes a refusal elsewhere
    attributable to the finding under test rather than to the fixture.
    """
    return InvoiceDraft(
        supplier_tax_id="ESB12345674",
        supplier_name="Proveedor Ejemplo SL",
        invoice_number="PROV-2024-0001",
        invoice_date="2024-11-15",
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("21.00"),
        grand_total=Decimal("121.00"),
        currency="EUR",
        provenance=(
            FieldProvenance(
                field="supplier_tax_id",
                origin=FieldOrigin.EXACT_STRUCTURED,
                grounding=FieldGroundingOutcome.ANCHORED,
                anchor="ESB12345674",
            ),
        ),
    )


def _draft_with_finding(kind: DraftDiscrepancyKind) -> InvoiceDraft:
    """The clean draft carrying exactly one deterministic finding of *kind*."""
    return _clean_draft().model_copy(
        update={
            "discrepancies": (
                DraftDiscrepancyFinding(
                    kind=kind,
                    field="grand_total",
                    detail=f"a genuine {kind.value} finding raised by the document's own figures",
                    expected=Decimal("121.00"),
                    observed=Decimal("126.20"),
                ),
            ),
        },
    )


def test_every_deterministic_check_declares_whether_it_blocks() -> None:
    """Completeness by construction over the closed check axis.

    Asserted against the enum, never against a copy of it: a hand-listed
    expectation would be updated in the same edit that adds a member and would
    therefore never catch the omission it exists to catch.
    """
    assert set(BLOCKING_REASON_BY_DISCREPANCY_KIND) == set(DraftDiscrepancyKind)
    assert set(BLOCKING_REASON_BY_DISCREPANCY_KIND.values()) <= set(ConfirmationBlockReason)


def test_a_document_raising_no_finding_confirms_cleanly() -> None:
    """Positive control. Without it, "the gate refuses" is satisfied by refusing always."""
    assert confirmation_blockers(_clean_draft()) == ()
    assert resolved_blockers(draft=_clean_draft(), resolutions=()) == ()


@pytest.mark.parametrize(
    ("kind", "expected_reason"),
    [
        (DraftDiscrepancyKind.ARITHMETIC_CLOSURE, ConfirmationBlockReason.CLOSURE_DISCREPANCY),
        (DraftDiscrepancyKind.RATE_INCONSISTENT, ConfirmationBlockReason.CLOSURE_DISCREPANCY),
        (DraftDiscrepancyKind.BREAKDOWN_INCONSISTENT, ConfirmationBlockReason.CLOSURE_DISCREPANCY),
        (DraftDiscrepancyKind.IDENTITY_UNVERIFIED, ConfirmationBlockReason.AMBIGUOUS_IDENTITY),
        (DraftDiscrepancyKind.ROLE_UNRESOLVED, ConfirmationBlockReason.UNRESOLVED_DIRECTION),
        (DraftDiscrepancyKind.INVOICE_CLASS_UNMODELLED, ConfirmationBlockReason.UNMODELLED_INVOICE_CLASS),
        (DraftDiscrepancyKind.INVOICE_CLASS_CONTRADICTED, ConfirmationBlockReason.CONTRADICTED_INVOICE_CLASS),
    ],
)
def test_each_finding_class_refuses_the_confirm_until_it_is_answered(
    kind: DraftDiscrepancyKind,
    expected_reason: ConfirmationBlockReason,
) -> None:
    """One refusal per finding class, and the refusal names the finding.

    The message is asserted on the CODE-side identifiers --- the blocker id and
    the reason token --- never on prose, which is localised and would make this
    test a translation gate.
    """
    draft = _draft_with_finding(kind)
    blockers = confirmation_blockers(draft)

    assert [blocker.reason for blocker in blockers] == [expected_reason]

    with pytest.raises(ConfirmationBlockedError) as raised:
        resolved_blockers(draft=draft, resolutions=())

    # The identifiers ride on the refusal's facts, never in an authored
    # sentence: str(exc) would otherwise carry English into every locale.
    carried = str(raised.value.context or {})
    assert blockers[0].blocker_id in carried
    assert expected_reason.value in carried


def test_an_ambiguous_counterparty_identifier_blocks_without_any_arithmetic_finding() -> None:
    """The second blocker source: a grounding outcome, not a failed identity.

    An ambiguous tax identifier raises no arithmetic finding at all, so a gate
    built only on the discrepancy list would let the operator confirm a record
    naming whichever of two real taxpayers the reader happened to list first.
    """
    draft = _clean_draft().model_copy(
        update={
            "provenance": (
                FieldProvenance(
                    field="supplier_tax_id",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=(
                        FieldAmbiguityCandidate(value="ESB12345674", note="header block"),
                        FieldAmbiguityCandidate(value="ESX1234567L", note="footer block"),
                    ),
                    note="two tax ids printed on the same document",
                ),
            ),
        },
    )

    blockers = confirmation_blockers(draft)

    assert [blocker.reason for blocker in blockers] == [ConfirmationBlockReason.AMBIGUOUS_IDENTITY]
    assert blockers[0].candidate_values == ("ESB12345674", "ESX1234567L")
    with pytest.raises(ConfirmationBlockedError):
        resolved_blockers(draft=draft, resolutions=())


def test_an_ambiguous_soft_field_does_not_block() -> None:
    """Scope control: only an ambiguous COUNTERPARTY blocks, not any ambiguity.

    Without this, the previous test would pass under a gate that blocks on every
    ambiguous field, and the named identity scope would be untested.
    """
    draft = _clean_draft().model_copy(
        update={
            "provenance": (
                FieldProvenance(
                    field="supplier_name",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=(
                        FieldAmbiguityCandidate(value="Proveedor Ejemplo SL"),
                        FieldAmbiguityCandidate(value="Proveedor Ejemplo, S.L."),
                    ),
                ),
            ),
        },
    )

    assert confirmation_blockers(draft) == ()


def test_answering_one_of_two_findings_still_refuses() -> None:
    """There is no partial pass, which is the shape a bulk flag would create.

    A gate that cleared once ANY finding was answered would be a bulk confirm
    reached by a different route: one keystroke, every blocker gone.
    """
    draft = _clean_draft().model_copy(
        update={
            "discrepancies": (
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ARITHMETIC_CLOSURE,
                    field="grand_total",
                    detail="the printed total does not equal the components",
                ),
                DraftDiscrepancyFinding(
                    kind=DraftDiscrepancyKind.ROLE_UNRESOLVED,
                    field=None,
                    detail="nothing on the page distinguishes issuer from recipient",
                ),
            ),
        },
    )
    blockers = confirmation_blockers(draft)
    assert len(blockers) == 2

    with pytest.raises(ConfirmationBlockedError) as raised:
        resolved_blockers(
            draft=draft,
            resolutions=(
                FindingResolution(
                    blocker_id=blockers[0].blocker_id,
                    action=FindingResolutionAction.ATTEST,
                    note="checked against the paper invoice; the recargo line is real",
                ),
            ),
        )

    carried = str(raised.value.context or {})
    assert blockers[1].blocker_id in carried
    assert blockers[0].blocker_id not in carried


def test_answering_every_finding_lets_the_confirm_through() -> None:
    """The gate opens, and only when each finding carries its own answer."""
    draft = _draft_with_finding(DraftDiscrepancyKind.ARITHMETIC_CLOSURE)
    blockers = confirmation_blockers(draft)

    cleared = resolved_blockers(
        draft=draft,
        resolutions=(
            FindingResolution(
                blocker_id=blockers[0].blocker_id,
                action=FindingResolutionAction.ATTEST,
                note="the document prints a suplido this draft cannot represent",
            ),
        ),
    )

    assert cleared == blockers


def test_a_resolution_naming_no_finding_refuses_rather_than_passing_silently() -> None:
    """A mistyped id must not read as an answer to something else.

    Accepting it silently is the failure where an operator believes they
    answered a finding and the confirm proceeded on a different one.
    """
    draft = _draft_with_finding(DraftDiscrepancyKind.ARITHMETIC_CLOSURE)

    with pytest.raises(ConfirmationBlockedError) as raised:
        resolved_blockers(
            draft=draft,
            resolutions=(
                FindingResolution(
                    blocker_id="0123456789abcdef",
                    action=FindingResolutionAction.ATTEST,
                    note="answering a finding that does not exist",
                ),
            ),
        )

    # The mistyped id is named as a fact, so an operator (or an agent) can see
    # WHICH id was rejected without parsing a localised sentence.
    assert (raised.value.context or {}).get("blocker_id") == "0123456789abcdef"


def test_choosing_a_value_the_document_never_offered_refuses() -> None:
    """A choice is between recorded candidates; anything else is an assertion.

    Letting a ``choose`` carry an unlisted value would let the strongest-looking
    action --- "the operator picked the reading the document offered" --- record
    a value the document never printed.
    """
    draft = _clean_draft().model_copy(
        update={
            "provenance": (
                FieldProvenance(
                    field="supplier_tax_id",
                    origin=FieldOrigin.TEXT_LAYER,
                    grounding=FieldGroundingOutcome.AMBIGUOUS,
                    candidates=(
                        FieldAmbiguityCandidate(value="ESB12345674"),
                        FieldAmbiguityCandidate(value="ESX1234567L"),
                    ),
                ),
            ),
        },
    )
    blockers = confirmation_blockers(draft)

    # The refusal no longer echoes the supplied value or the competing ones. It
    # names the DIGESTS the review surface rendered, which is what the operator
    # can check their answer against -- and printing the raw candidates put the
    # very identity this blocker exists to protect into a refusal message.
    with pytest.raises(ConfirmationBlockedError):
        resolved_blockers(
            draft=draft,
            resolutions=(
                FindingResolution(
                    blocker_id=blockers[0].blocker_id,
                    action=FindingResolutionAction.CHOOSE_CANDIDATE,
                    value="ESA00000000",
                ),
            ),
        )

    # Positive control on the same blocker: a listed candidate is accepted, so
    # the refusal above is attributable to the value and not to the action.
    assert (
        resolved_blockers(
            draft=draft,
            resolutions=(
                FindingResolution(
                    blocker_id=blockers[0].blocker_id,
                    action=FindingResolutionAction.CHOOSE_CANDIDATE,
                    value="ESX1234567L",
                ),
            ),
        )
        == blockers
    )


def test_an_attestation_with_no_stated_reason_is_refused_at_construction() -> None:
    """An attestation is a stated basis, not a waiver wearing a resolution's shape."""
    with pytest.raises(ValidationError, match="attestation"):
        FindingResolution(blocker_id="0123456789abcdef", action=FindingResolutionAction.ATTEST)

    with pytest.raises(ValidationError, match="attestation"):
        FindingResolution(
            blocker_id="0123456789abcdef",
            action=FindingResolutionAction.ATTEST,
            value="121.00",
            note="stating a value while attesting",
        )


def test_blocker_ids_are_clock_free_and_stable_across_re_reads() -> None:
    """The same unchanged document raises the same ids every time.

    An id folding the clock would refuse every resolution captured from an
    earlier listing, and the operator would learn to re-run and re-copy instead
    of to answer.
    """
    first = confirmation_blockers(_draft_with_finding(DraftDiscrepancyKind.ARITHMETIC_CLOSURE))
    second = confirmation_blockers(_draft_with_finding(DraftDiscrepancyKind.ARITHMETIC_CLOSURE))

    assert [blocker.blocker_id for blocker in first] == [blocker.blocker_id for blocker in second]
    assert (
        first[0].blocker_id
        != confirmation_blockers(
            _draft_with_finding(DraftDiscrepancyKind.ROLE_UNRESOLVED),
        )[0].blocker_id
    )
