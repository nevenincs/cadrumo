"""A document that contradicts its own declared regime cannot be confirmed past.

The finding and its enrolment. A mention whose whole point is that the issuer
charges no Spanish IVA, printed beside a repercutido line, means the mention or
the line does not belong -- and which one is not decidable from the page, because
either reading leads to a different declaration.

**The two contradiction shapes collapse into one reachable check, and that is
stated rather than worked around.** A contradiction needs a mention that declares
a category, and the statutory table has exactly one -- which is also the only row
declaring ``expects_repercutido_line=False``. So "a reverse-charge mention beside
a charged line" and "a mention the rate pattern belies" are not two shapes today:
they are the same row, checked in the only direction it can fail. The other six
mentions declare nothing to contradict, and the exempt case fixes no phrase at
all (art. 6.1.j requires a reference to the granting provision, not a set
string), so there is nothing to match.

**The second direction becomes reachable only when a row declares a category with
``expects_repercutido_line=True``** -- a mention whose regime DOES expect Spanish
IVA, contradicted by a document printing none. No such row exists, so a refusal
case for it would exercise a branch no legend can reach, which is the
fixtures-too-easy failure at design level. Naming the condition is worth more
than a test that cannot fail, and the premise test below pins the count so the
claim cannot go stale in silence.

**The positive control is load-bearing.** Every refusal case below passes equally
against a gate that refuses everything, so a coherent document is confirmed to
still pass cleanly. Without it "blocks on contradiction" is unmeasured.

See Also:
    :func:`~application.ledger.regime_contradiction.regime_contradiction_finding`
        The producer under test.
    :data:`~application.ledger.confirmation_gate.BLOCKING_REASON_BY_DISCREPANCY_KIND`
        Where the finding's kind becomes a refusal the confirm gate honours.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.confirmation_gate import ConfirmationBlockReason
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....domain.iva.regime_legend import REGIME_LEGENDS, RegimeLegend
from ..confirmation_gate import BLOCKING_REASON_BY_DISCREPANCY_KIND, confirmation_blockers
from ..evidence_draft import InvoiceDraft
from ..regime_contradiction import draft_prints_a_repercutido_line, regime_contradiction_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DECLARING = tuple(legend for legend in REGIME_LEGENDS if legend.declares is not None)
_SILENT = tuple(legend for legend in REGIME_LEGENDS if legend.declares is None)
_REVERSE_CHARGE_MENTION = _DECLARING[0].phrase


def test_only_one_contradiction_shape_is_reachable() -> None:
    """The premise this module's scope rests on, asserted rather than claimed in prose.

    Two facts collapse the two nominal shapes into one. A contradiction needs a
    mention that DECLARES a category, and exactly one does; that same row is the
    only one expecting no repercutido line, so the only way it can be
    contradicted is by a document printing one.

    Both halves are asserted, because either changing reopens the second
    direction. A row that declares a category while expecting a repercutido line
    would be contradicted by a document printing NONE -- the shape this suite
    deliberately does not cover, since no such row exists.
    """
    assert len(_DECLARING) == 1
    assert _DECLARING[0].expects_repercutido_line is False
    assert not [legend for legend in REGIME_LEGENDS if legend.declares is not None and legend.expects_repercutido_line]


def test_a_reverse_charge_mention_beside_a_charged_cuota_is_a_finding() -> None:
    """The reachable shape: the words say no Spanish IVA, the figures charge it."""
    draft = InvoiceDraft(
        regime_legend=_REVERSE_CHARGE_MENTION,
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
    )

    finding = regime_contradiction_finding(draft)

    assert finding is not None
    assert finding.kind is DraftDiscrepancyKind.REGIME_CONTRADICTED
    # Points at the mention, not the category: the category was never
    # established, so naming it would send the operator to a value that does not
    # exist on the record.
    assert finding.field == "regime_legend"
    assert finding.detail


def test_a_stated_rate_alone_contradicts_even_with_no_legible_cuota() -> None:
    """A printed "IVA 21%" is a claim that tax was charged, cuota or not."""
    draft = InvoiceDraft(
        regime_legend=_REVERSE_CHARGE_MENTION,
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
    )

    assert regime_contradiction_finding(draft) is not None


def test_the_coherent_reverse_charge_document_raises_nothing() -> None:
    """The positive control. Without it every case above passes on a gate that always refuses."""
    draft = InvoiceDraft(
        regime_legend=_REVERSE_CHARGE_MENTION,
        taxable_base=Decimal("1000.00"),
        grand_total=Decimal("1000.00"),
    )

    assert regime_contradiction_finding(draft) is None


def test_a_zero_rate_beside_the_mention_is_the_ordinary_presentation_not_a_conflict() -> None:
    """A reverse-charge invoice may print zeroes to SHOW no tax was charged.

    Reading a printed zero as tax charged would fire on exactly the documents
    this check exists to respect, which is the shape of a check that looks
    strict and is simply wrong.
    """
    draft = InvoiceDraft(
        regime_legend=_REVERSE_CHARGE_MENTION,
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0.00"),
        grand_total=Decimal("1000.00"),
    )

    assert regime_contradiction_finding(draft) is None


@pytest.mark.parametrize("legend", _SILENT, ids=lambda legend: legend.provision)
def test_a_mention_that_declares_no_category_cannot_contradict(legend: RegimeLegend) -> None:
    """Six mentions are real obligations that fix no category, so there is nothing to conflict with."""
    draft = InvoiceDraft(
        regime_legend=legend.phrase,
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("210.00"),
    )

    assert regime_contradiction_finding(draft) is None


def test_an_ordinary_invoice_with_no_mention_raises_nothing() -> None:
    """Most invoices print no mandated mention and state no regime to check."""
    draft = InvoiceDraft(
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("21"),
        iva_amount=Decimal("210.00"),
        grand_total=Decimal("1210.00"),
    )

    assert regime_contradiction_finding(draft) is None


class TestTheRepercutidoSignal:
    """What counts as output IVA on the face of the document."""

    def test_a_positive_cuota_counts(self) -> None:
        assert draft_prints_a_repercutido_line(InvoiceDraft(iva_amount=Decimal("210.00"))) is True

    def test_a_positive_rate_counts(self) -> None:
        assert draft_prints_a_repercutido_line(InvoiceDraft(iva_rate=Decimal("21"))) is True

    def test_zeroes_do_not_count(self) -> None:
        draft = InvoiceDraft(iva_rate=Decimal("0"), iva_amount=Decimal("0.00"))
        assert draft_prints_a_repercutido_line(draft) is False

    def test_absent_figures_do_not_count(self) -> None:
        assert draft_prints_a_repercutido_line(InvoiceDraft()) is False


class TestTheFindingIsEnrolledAsBlocking:
    """A finding that does not block is a finding the operator never sees stop them."""

    def test_the_kind_maps_to_a_refusal_reason(self) -> None:
        assert (
            BLOCKING_REASON_BY_DISCREPANCY_KIND[DraftDiscrepancyKind.REGIME_CONTRADICTED]
            is ConfirmationBlockReason.CONTRADICTED_REGIME
        )

    def test_the_mapping_is_total_over_the_enum_itself(self) -> None:
        """Asserted against the enum rather than a copy, so it cannot be defeated in one edit."""
        assert set(BLOCKING_REASON_BY_DISCREPANCY_KIND) == set(DraftDiscrepancyKind)

    def test_a_contradicted_draft_produces_a_blocker(self) -> None:
        """The finding reaches the gate, which is the property the mapping exists for."""
        draft = InvoiceDraft(
            regime_legend=_REVERSE_CHARGE_MENTION,
            taxable_base=Decimal("1000.00"),
            iva_rate=Decimal("21"),
            iva_amount=Decimal("210.00"),
            grand_total=Decimal("1210.00"),
        )
        finding = regime_contradiction_finding(draft)
        assert finding is not None

        blockers = confirmation_blockers(draft=draft.model_copy(update={"discrepancies": (finding,)}))

        assert any(blocker.reason is ConfirmationBlockReason.CONTRADICTED_REGIME for blocker in blockers)

    def test_a_coherent_draft_produces_no_contradiction_blocker(self) -> None:
        """The negative case carried through the same producer-to-gate wire as the positive.

        The gate reads findings off the draft; it does not run the producer. So a
        coherent draft handed to it bare raises no contradiction blocker whatever
        the producer does, and asserting that measures nothing -- the shape this
        case previously had, under a docstring that vouched for the coverage it
        lacked. The producer runs here for real, exactly as it does in the
        contradicted case above, and whatever it returns is stamped before the
        gate is asked -- deliberately without asserting the producer's answer
        first. An intermediate ``assert finding is None`` would red on the
        producer line and the gate assertion below would never execute, leaving
        the very claim this case makes unexercised. The stamping adapter is the
        one the shared check list uses, so a producer that started firing on a
        coherent document would reach the gate here exactly as it would in
        production.
        """
        draft = InvoiceDraft(
            regime_legend=_REVERSE_CHARGE_MENTION,
            taxable_base=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
        )
        finding = regime_contradiction_finding(draft)
        stamped = draft.model_copy(update={"discrepancies": () if finding is None else (finding,)})

        blockers = confirmation_blockers(draft=stamped)

        assert not any(blocker.reason is ConfirmationBlockReason.CONTRADICTED_REGIME for blocker in blockers)
