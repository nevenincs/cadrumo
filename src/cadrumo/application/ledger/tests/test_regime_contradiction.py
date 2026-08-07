"""A document that contradicts its own declared regime cannot be confirmed past.

The finding and its enrolment. A mention whose whole point is that the issuer
charges no Spanish IVA, printed beside a repercutido line, means the mention or
the line does not belong -- and which one is not decidable from the page, because
either reading leads to a different declaration.

**Only one contradiction shape is reachable today, and that is stated rather than
worked around.** The statutory table carries seven mandated mentions and exactly
one declares a category, so a contradiction requires that one mention. The other
six declare nothing to contradict, and the exempt case fixes no phrase at all
(art. 6.1.j requires a reference to the granting provision, not a set string), so
there is nothing to match. Writing a refusal case per hypothetical shape would
report broad coverage over branches no document can reach; the reachable shape is
covered here and a premise test pins the table so this claim cannot go stale
silently.

**The positive control is load-bearing.** Every refusal case below passes equally
against a gate that refuses everything, so a coherent document is confirmed to
still pass cleanly. Without it "blocks on contradiction" is unmeasured.

See Also:
    :func:`~application.ledger.regime_contradiction_finding`
        The producer under test.
    :data:`~application.ledger.BLOCKING_REASON_BY_DISCREPANCY_KIND`
        Where the finding's kind becomes a refusal the confirm gate honours.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core import ConfirmationBlockReason, DraftDiscrepancyKind
from ....domain.iva import REGIME_LEGENDS
from .._confirmation_gate import BLOCKING_REASON_BY_DISCREPANCY_KIND, confirmation_blockers
from .._evidence_draft import InvoiceDraft
from .._regime_contradiction import draft_prints_a_repercutido_line, regime_contradiction_finding

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_DECLARING = tuple(legend for legend in REGIME_LEGENDS if legend.declares is not None)
_SILENT = tuple(legend for legend in REGIME_LEGENDS if legend.declares is None)
_REVERSE_CHARGE_MENTION = _DECLARING[0].phrase


def test_only_one_contradiction_shape_is_reachable() -> None:
    """The premise this module's scope rests on, asserted rather than claimed in prose.

    A contradiction needs a mention that declares a category. If a second such
    row is ever added, the reachable set grows and this suite stops covering it
    -- and says so here instead of continuing to read as complete.
    """
    assert len(_DECLARING) == 1
    assert _DECLARING[0].expects_repercutido_line is False


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
def test_a_mention_that_declares_no_category_cannot_contradict(legend: object) -> None:
    """Six mentions are real obligations that fix no category, so there is nothing to conflict with."""
    draft = InvoiceDraft(
        regime_legend=legend.phrase,  # type: ignore[attr-defined]
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
        """The positive control at the gate, not only at the producer."""
        draft = InvoiceDraft(
            regime_legend=_REVERSE_CHARGE_MENTION,
            taxable_base=Decimal("1000.00"),
            grand_total=Decimal("1000.00"),
        )

        blockers = confirmation_blockers(draft=draft)

        assert not any(blocker.reason is ConfirmationBlockReason.CONTRADICTED_REGIME for blocker in blockers)
