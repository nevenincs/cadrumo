"""One meaning per term, proven from the producer through to the closure check.

The defect this gates is not a formatting drift, it is a SEMANTIC one, and no
single-hop test could see it. Extraction wrote the printed-total identity's cuota
term as cuota PLUS recargo de equivalencia, because the source format states a
combined output-tax figure under a name the draft uses for the cuota alone. The
closure check then read that term as the cuota and added the recargo a second
time from its own slot. Both hops were locally defensible; only their composition
was wrong.

What that cost is the whole reason this file exists. A bundled Facturae document
whose printed arithmetic closes exactly -- ``100,00 + 21,00 + 5,20 = 126,20`` --
was reported inconsistent by exactly the recargo, so a blocking closure finding
fired at the confirm boundary for every recargo de equivalencia filer. A common
Spanish regime, refused on a correct invoice.

The canonical declaration already existed and is machine-enforced:
:class:`~domain.invoices.InvoiceComponents` validates
``total = taxable_base + cuota + recargo + suplido`` and ``cash = total -
retencion``. The producer simply never derived from it. So these gates bind both
ends to that one declaration rather than to each other: the consumer is proven to
implement the canonical identity, and the producer is proven to emit the
canonical cuota term.

Assertions here key on the NUMBERS and the term semantics, never on which finding
kind fired. Two different documents reach ``ARITHMETIC_CLOSURE`` for opposite
reasons -- one omits the recargo, one double-counts it -- so a gate keyed on the
kind alone would pass while the double-count survived.

See Also:
    :class:`~domain.invoices.InvoiceComponents`
        The canonical, validator-enforced statement of the identity.
    :func:`~application.ledger.closure_findings`
        The consumer under gate.
"""

from __future__ import annotations

import pathlib
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.inbound.einvoice._parsers import parse_einvoice_document
from ....core.draft_discrepancy import DraftDiscrepancyKind
from ....domain.invoices.decomposition import InvoiceComponents
from ..closure_findings import closure_findings
from ..invoice_draft_records import InvoiceDraft

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CORPUS = pathlib.Path(__file__).parent / "_evidence_corpus"

#: The bundled Facturae document, whose printed arithmetic is verified correct:
#: base 100,00 + cuota 21,00 + recargo 5,20 = total 126,20. Not synthesised here
#: -- a fixture authored to match the fix would prove only that it matches.
_RECARGO_DOCUMENT = "facturae_32_recargo_invoice.xml"

_BASE = Decimal("100.00")
_CUOTA = Decimal("21.00")
_RECARGO = Decimal("5.20")
_TOTAL = Decimal("126.20")


def _closure_kinds(draft: InvoiceDraft) -> list[DraftDiscrepancyKind]:
    return [finding.kind for finding in closure_findings(draft)]


def _draft(
    *,
    taxable_base: Decimal | None = _BASE,
    iva_amount: Decimal | None = _CUOTA,
    recargo_amount: Decimal | None = _RECARGO,
    grand_total: Decimal | None = _TOTAL,
    retencion_rate: Decimal | None = None,
    retencion_amount: Decimal | None = None,
) -> InvoiceDraft:
    """Build a draft over the bundled document's figures, one term at a time."""
    return InvoiceDraft(
        taxable_base=taxable_base,
        iva_rate=Decimal("21"),
        iva_amount=iva_amount,
        recargo_amount=recargo_amount,
        grand_total=grand_total,
        retencion_rate=retencion_rate,
        retencion_amount=retencion_amount,
    )


class TestTheProducerEmitsTheIdentitysCuotaTerm:
    """The structured reader must write the cuota, not total output tax.

    The source format states ``TotalTaxOutputs`` -- cuota plus surcharge -- and
    the per-band ``TaxAmount`` beside a sibling ``EquivalenceSurchargeAmount``.
    Only the second is the identity's cuota by construction, which is why the
    reader takes the bands rather than correcting the combined figure afterwards:
    a term read from a source that cannot contain the surcharge cannot acquire
    one.
    """

    def test_the_bundled_recargo_document_yields_cuota_alone(self) -> None:
        parsed = parse_einvoice_document((_CORPUS / _RECARGO_DOCUMENT).read_bytes())

        assert parsed.taxable_base == _BASE
        assert parsed.iva_amount == _CUOTA, "the cuota term must exclude the recargo carried beside it"
        assert parsed.recargo_amount == _RECARGO
        assert parsed.grand_total == _TOTAL

    def test_the_cuota_term_equals_the_band_sum(self) -> None:
        """The identity every sibling corpus test asserts, and this one lacked.

        Its absence here is why the double-count survived: the recargo fixture
        checked the breakdown and the surcharge but never the scalar the
        breakdown is supposed to sum to.
        """
        parsed = parse_einvoice_document((_CORPUS / _RECARGO_DOCUMENT).read_bytes())

        band_cuotas = sum(
            (cuota for _rate, _base, cuota in parsed.iva_breakdown if cuota is not None),
            Decimal("0"),
        )

        assert band_cuotas == parsed.iva_amount

    def test_the_printed_total_closes_over_the_produced_terms(self) -> None:
        """The regression, stated as arithmetic rather than as a finding kind."""
        parsed = parse_einvoice_document((_CORPUS / _RECARGO_DOCUMENT).read_bytes())
        assert parsed.taxable_base is not None
        assert parsed.iva_amount is not None
        assert parsed.recargo_amount is not None

        assert parsed.taxable_base + parsed.iva_amount + parsed.recargo_amount == parsed.grand_total


class TestTheConsumerAcceptsACorrectRecargoInvoiceAndStillCatchesABrokenOne:
    """Silence on a correct document is only meaningful beside a caught wrong one."""

    def test_a_recargo_document_whose_arithmetic_closes_raises_no_closure_finding(self) -> None:
        """The regression: the defect's own input shape, driven end to end."""
        parsed = parse_einvoice_document((_CORPUS / _RECARGO_DOCUMENT).read_bytes())
        draft = _draft(
            taxable_base=parsed.taxable_base,
            iva_amount=parsed.iva_amount,
            recargo_amount=parsed.recargo_amount,
            grand_total=parsed.grand_total,
        )

        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE not in _closure_kinds(draft)

    def test_the_double_counted_shape_is_still_reported(self) -> None:
        """The pre-fix producer output, pinned so the defect cannot return silently.

        Keyed on the figures rather than the kind: this is the shape where the
        cuota term carries the surcharge AND the surcharge is stated again in its
        own slot, which is a different fault from a document that simply omits
        one.
        """
        draft = _draft(iva_amount=_CUOTA + _RECARGO, recargo_amount=_RECARGO)

        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in _closure_kinds(draft)

    def test_a_genuinely_wrong_total_is_still_caught(self) -> None:
        """The positive control: "no finding" must not be satisfiable by silence."""
        draft = _draft(grand_total=_TOTAL + Decimal("10.00"))

        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in _closure_kinds(draft)

    def test_a_document_omitting_the_recargo_is_a_different_fault_from_double_counting(self) -> None:
        """Two shapes, one finding kind, opposite causes.

        Recorded because a gate keyed on the kind cannot tell them apart, and
        reading either as evidence about the other is how a false all-clear gets
        issued on this defect.
        """
        omitted = _draft(recargo_amount=None)
        doubled = _draft(iva_amount=_CUOTA + _RECARGO)

        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in _closure_kinds(omitted)
        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE in _closure_kinds(doubled)
        assert omitted.iva_amount != doubled.iva_amount


class TestTheConsumerImplementsTheCanonicalIdentity:
    """Both ends bind to the one declaration, not to each other.

    Driven by feeding the same figures to the validator-enforced canonical model
    and to the closure check: a component set the canonical identity ACCEPTS must
    raise no closure finding, and one it could not represent must.
    """

    def test_a_component_set_the_canonical_identity_accepts_closes_cleanly(self) -> None:
        components = InvoiceComponents(
            taxable_base=_BASE,
            cuota=_CUOTA,
            retencion=Decimal("0"),
            recargo=_RECARGO,
            suplido=Decimal("0"),
            total=_TOTAL,
            cash=_TOTAL,
        )
        draft = _draft(
            taxable_base=components.taxable_base,
            iva_amount=components.cuota,
            recargo_amount=components.recargo,
            grand_total=components.total,
        )

        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE not in _closure_kinds(draft)

    def test_the_canonical_identity_refuses_the_double_counted_split(self) -> None:
        """The producer defect, expressed against the declaration it violated."""
        with pytest.raises(ValidationError, match="total must equal"):
            InvoiceComponents(
                taxable_base=_BASE,
                cuota=_CUOTA + _RECARGO,
                retencion=Decimal("0"),
                recargo=_RECARGO,
                suplido=Decimal("0"),
                total=_TOTAL,
                cash=_TOTAL,
            )

    def test_retencion_is_outside_the_total_on_both_sides(self) -> None:
        """A settlement-side deduction, never a price component.

        Pinned because the draft grew withholding fields, and folding them into
        the closure sum is the plausible next version of this same defect: the
        canonical identity puts retencion between total and cash, so a withheld
        invoice whose total closes must stay clean.
        """
        components = InvoiceComponents(
            taxable_base=_BASE,
            cuota=_CUOTA,
            retencion=Decimal("15.00"),
            recargo=_RECARGO,
            suplido=Decimal("0"),
            total=_TOTAL,
            cash=_TOTAL - Decimal("15.00"),
        )
        draft = _draft(retencion_rate=Decimal("15"), retencion_amount=components.retencion)

        assert components.total == _TOTAL
        assert DraftDiscrepancyKind.ARITHMETIC_CLOSURE not in _closure_kinds(draft)
