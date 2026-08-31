"""Behavioural tests for the invoice decomposition contract.

The contract's whole reason to exist is that a partial record must stay
visible, so these cases assert the two things that would quietly undo it: that
an ungrounded record is neither refused at construction nor filtered into
nothing, and that the grounded/excluded verdict cannot be read ambiguously off
a null.

The euro figures asserted here are the contract's own identity
(``total = taxable_base + cuota``, ``cash = total - retención``), which is what
this module implements; the legal content under test is *which* records the
Axis-A table admits, and every case would change verdict if that table's
grounding changed.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....adapters.outbound.fx._ecb_provider import ECB_RATE_SOURCE_ID
from ...iva.classification import InvoiceKind, TransactionKind
from ...iva.oss import OssIossRegime
from ...iva.schema import EUMemberState, IvaCategory, IvaRateKind
from ..decomposition import (
    INVOICE_DECOMPOSITION_DEFECT_GUIDANCE,
    InvoiceComponents,
    InvoiceDecomposition,
    InvoiceDecompositionDefect,
    decompose_invoice,
    partition_invoices,
)
from ..enums import IvaRate, PaymentStatus, iva_rate_percentage
from ..models import Invoice, InvoiceLine

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _line(*, unit_price: str = "1000.00", iva_rate: IvaRate = IvaRate.RATE_21, **extra: object) -> InvoiceLine:
    subtotal = Decimal(unit_price)
    rate = iva_rate_percentage(iva_rate)
    iva_amount = Decimal("0") if rate is None else subtotal * rate
    return InvoiceLine.model_validate(
        {
            "description": "Servicios profesionales",
            "quantity": Decimal("1"),
            "unit_price": subtotal,
            "subtotal": subtotal,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            **extra,
        },
    )


def _invoice(
    *,
    lines: tuple[InvoiceLine, ...] | None = None,
    invoice_number: str = "F-2026-001",
    counterparty_country: str = "ES",
    counterparty_tax_id: str = "B12345674",
    currency: str = "EUR",
    **extra: object,
) -> Invoice:
    resolved_lines = lines if lines is not None else (_line(),)
    base_total = sum((line.subtotal for line in resolved_lines), start=Decimal("0"))
    iva_total = sum((line.iva_amount for line in resolved_lines), start=Decimal("0"))
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": invoice_number,
            "issued_at": date(2026, 4, 1),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": counterparty_tax_id,
            "counterparty_country": counterparty_country,
            "base_total": base_total,
            "iva_total": iva_total,
            "grand_total": base_total + iva_total,
            "currency": currency,
            "lines": resolved_lines,
            "payment_status": PaymentStatus.PAID,
            **extra,
        },
    )


def test_domestic_rated_invoice_decomposes_into_the_canonical_identity() -> None:
    """A fully declared invoice yields base, cuota, total and cash."""
    invoice = _invoice(
        iva_category=IvaCategory.DOMESTIC_GENERAL,
        retention_rate=Decimal("0.15"),
        retention_amount=Decimal("150.00"),
    )

    verdict = decompose_invoice(invoice)

    assert verdict.is_grounded
    assert verdict.defects == ()
    components = verdict.components
    assert components is not None
    assert components.taxable_base == Decimal("1000.00")
    assert components.cuota == Decimal("210.00")
    assert components.retencion == Decimal("150.00")
    assert components.total == Decimal("1210.00")
    assert components.cash == Decimal("1060.00")


def test_retencion_leaves_the_total_untouched_and_reduces_only_the_cash() -> None:
    """The same operation costs the same whether or not it is withheld from."""
    without = decompose_invoice(_invoice(iva_category=IvaCategory.DOMESTIC_GENERAL))
    with_retencion = decompose_invoice(
        _invoice(
            iva_category=IvaCategory.DOMESTIC_GENERAL,
            retention_rate=Decimal("0.15"),
            retention_amount=Decimal("150.00"),
        ),
    )

    assert without.components is not None
    assert with_retencion.components is not None
    assert without.components.total == with_retencion.components.total
    assert without.components.cash - with_retencion.components.cash == Decimal("150.00")


def test_exempt_invoice_is_grounded_with_a_real_base_and_zero_cuota() -> None:
    """Cuota-less is not substrate-less: an exempt supply still decomposes."""
    invoice = _invoice(
        lines=(_line(iva_rate=IvaRate.EXEMPT),),
        iva_category=IvaCategory.DOMESTIC_EXEMPT,
    )

    verdict = decompose_invoice(invoice)

    assert verdict.is_grounded
    assert verdict.components is not None
    assert verdict.components.taxable_base == Decimal("1000.00")
    assert verdict.components.cuota == Decimal("0")


def test_invoice_without_a_declared_iva_treatment_is_excluded() -> None:
    """Amounts alone cannot say whether the operation was exempt or untagged."""
    verdict = decompose_invoice(_invoice())

    assert not verdict.is_grounded
    assert verdict.components is None
    assert verdict.defects == (InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED,)
    assert verdict.category is None


@pytest.mark.parametrize("category", [IvaCategory.UNKNOWN, IvaCategory.ERRONEOUS_INVOICE])
def test_placeholder_categories_are_excluded_via_their_axis_a_row(category: IvaCategory) -> None:
    """A category whose own components are unknown grounds nothing."""
    verdict = decompose_invoice(_invoice(iva_category=category))

    assert verdict.defects == (InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED,)
    assert verdict.category is category


def test_cuota_recorded_against_a_zero_by_law_category_is_excluded() -> None:
    """A cuota on an exempt supply means one of the two declarations is wrong."""
    verdict = decompose_invoice(_invoice(iva_category=IvaCategory.DOMESTIC_EXEMPT))

    assert verdict.defects == (InvoiceDecompositionDefect.CUOTA_CONTRADICTS_CATEGORY,)


def test_invoice_with_no_taxable_base_is_excluded_where_the_category_requires_one() -> None:
    """A category that carries a base grounds nothing without one recorded."""
    verdict = decompose_invoice(
        _invoice(
            lines=(_line(unit_price="0.00", iva_rate=IvaRate.EXEMPT),),
            iva_category=IvaCategory.DOMESTIC_EXEMPT,
        ),
    )

    assert verdict.defects == (InvoiceDecompositionDefect.TAXABLE_BASE_ABSENT,)


def test_defects_accumulate_so_one_pass_shows_everything_wrong() -> None:
    """An operator fixing a record should not discover defects one at a time."""
    verdict = decompose_invoice(
        _invoice(
            counterparty_country="US",
            counterparty_tax_id="US-TAX-1",
            currency="USD",
            lines=(_line(iva_rate=IvaRate.RATE_0),),
        ),
    )

    assert verdict.defects == (
        InvoiceDecompositionDefect.FX_UNRESOLVED,
        InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED,
    )


def test_oss_projected_invoice_keeps_its_destination_state_cuota() -> None:
    """An OSS cuota is the destination state's, not the Spanish general one."""
    invoice = _invoice(
        lines=(_line(unit_price="500.00", oss_rate_kind=IvaRateKind.GENERAL),),
        counterparty_country="DE",
        counterparty_tax_id="DE123456789",
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        oss_ioss_regime=OssIossRegime.UNION_SCHEME,
        oss_transaction_kind=TransactionKind.OSS_UNION_SERVICES,
    )

    verdict = decompose_invoice(invoice)

    assert verdict.is_grounded
    assert verdict.components is not None
    assert verdict.components.cuota == Decimal("105.00")


def test_unconverted_foreign_invoice_is_excluded_rather_than_approximated() -> None:
    """A foreign invoice with no resolved rate has no euro figure at all."""
    invoice = _invoice(
        counterparty_country="US",
        counterparty_tax_id="US-TAX-1",
        currency="USD",
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        lines=(_line(iva_rate=IvaRate.RATE_0),),
    )

    verdict = decompose_invoice(invoice)

    assert verdict.defects == (InvoiceDecompositionDefect.FX_UNRESOLVED,)


def test_converted_foreign_invoice_decomposes_in_euro() -> None:
    """With a resolved rate the components are the converted euro figures."""
    invoice = _invoice(
        counterparty_country="US",
        counterparty_tax_id="US-TAX-1",
        currency="USD",
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        lines=(_line(unit_price="200.00", iva_rate=IvaRate.RATE_0),),
        fx_rate=Decimal("0.90"),
        fx_rate_date=date(2026, 4, 1),
        fx_rate_source=ECB_RATE_SOURCE_ID,
    )

    verdict = decompose_invoice(invoice)

    assert verdict.is_grounded
    assert verdict.components is not None
    assert verdict.components.taxable_base == Decimal("180.00")
    assert verdict.components.total == Decimal("180.00")


def test_a_partial_record_is_still_a_valid_invoice() -> None:
    """The contract classifies; it never refuses the document at construction.

    An invoice the calculation cannot ground is a real document the taxpayer
    holds. Refusing to build it would delete the very record the operator has
    to be told about.
    """
    invoice = _invoice()

    assert invoice.invoice_id
    assert not decompose_invoice(invoice).is_grounded


def test_partition_keeps_the_excluded_records_alongside_the_usable_ones() -> None:
    """Nothing is dropped: both halves come back from one call."""
    grounded_invoice = _invoice(invoice_number="F-1", iva_category=IvaCategory.DOMESTIC_GENERAL)
    ungrounded_invoice = _invoice(invoice_number="F-2")

    partition = partition_invoices((grounded_invoice, ungrounded_invoice))

    assert [v.invoice_id for v in partition.grounded] == [grounded_invoice.invoice_id]
    assert [v.invoice_id for v in partition.ungrounded] == [ungrounded_invoice.invoice_id]
    assert partition.ungrounded[0].defects


def test_every_defect_carries_operator_guidance() -> None:
    """A new defect cannot ship without the sentence that tells an operator what to do."""
    assert set(INVOICE_DECOMPOSITION_DEFECT_GUIDANCE) == set(InvoiceDecompositionDefect)
    assert all(text.strip() for text in INVOICE_DECOMPOSITION_DEFECT_GUIDANCE.values())


def test_a_verdict_carrying_both_components_and_defects_is_refused() -> None:
    """The two outcome classes must stay mutually exclusive."""
    with pytest.raises(ValidationError, match="never both and never neither"):
        InvoiceDecomposition(
            invoice_id="a6f9a5d4eb5cf4f4f255b0d6d326ec2c81f9ec2cd7cf4272feaf8c0baaa458bd",
            category=IvaCategory.DOMESTIC_GENERAL,
            components=InvoiceComponents(
                taxable_base=Decimal("100"),
                cuota=Decimal("21"),
                retencion=Decimal("0"),
                recargo=Decimal("0"),
                suplido=Decimal("0"),
                total=Decimal("121"),
                cash=Decimal("121"),
            ),
            defects=(InvoiceDecompositionDefect.FX_UNRESOLVED,),
        )


def test_a_verdict_carrying_neither_components_nor_defects_is_refused() -> None:
    """An empty verdict would read as grounded-with-nothing."""
    with pytest.raises(ValidationError, match="never both and never neither"):
        InvoiceDecomposition(
            invoice_id="a6f9a5d4eb5cf4f4f255b0d6d326ec2c81f9ec2cd7cf4272feaf8c0baaa458bd",
            category=None,
            components=None,
            defects=(),
        )


def test_components_that_do_not_add_up_are_refused() -> None:
    """The identity is enforced on the components type itself."""
    with pytest.raises(ValidationError, match="total must equal taxable_base \\+ cuota"):
        InvoiceComponents(
            taxable_base=Decimal("100"),
            cuota=Decimal("21"),
            retencion=Decimal("0"),
            recargo=Decimal("0"),
            suplido=Decimal("0"),
            total=Decimal("999"),
            cash=Decimal("999"),
        )


def test_components_whose_cash_ignores_the_retencion_are_refused() -> None:
    """``cash`` is what the payer transfers, so the withholding must come off it."""
    with pytest.raises(ValidationError, match="cash must equal total - retencion"):
        InvoiceComponents(
            taxable_base=Decimal("100"),
            cuota=Decimal("21"),
            retencion=Decimal("15"),
            recargo=Decimal("0"),
            suplido=Decimal("0"),
            total=Decimal("121"),
            cash=Decimal("121"),
        )


def test_eu_member_state_substrate_still_resolves_for_a_partitioned_invoice() -> None:
    """The contract does not disturb the record's own accessors."""
    invoice = _invoice(
        counterparty_country="DE",
        counterparty_tax_id="DE123456789",
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        lines=(_line(iva_rate=IvaRate.EXEMPT),),
    )

    assert invoice.counterparty_eu_member_state is EUMemberState.DE
    assert decompose_invoice(invoice).is_grounded


def test_a_one_directional_category_on_its_impossible_side_is_its_own_defect() -> None:
    """An import the taxpayer ISSUED is a contradiction, not an absent declaration.

    LIVA art. 17 defines an importación as goods the taxpayer receives, so the
    pair (import_third_country, issued) describes no operation. The operator
    declared a treatment, so reporting it as IVA_TREATMENT_UNDECLARED would
    send them to fill in a field they already filled in; the two failures need
    different fixes and therefore different members.
    """
    invoice = _invoice(kind=InvoiceKind.ISSUED, iva_category=IvaCategory.IMPORT_THIRD_COUNTRY)

    defects = decompose_invoice(invoice).defects

    assert InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND in defects
    assert InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED not in defects


def test_the_same_category_on_its_real_side_is_not_flagged() -> None:
    """The control. Without it, a member that fired unconditionally would pass above.

    The identical category on the RECEIVED side is an ordinary importación, so
    the impossible-side defect must be absent — otherwise the check is keying
    on the category rather than on the pair.
    """
    invoice = _invoice(kind=InvoiceKind.RECEIVED, iva_category=IvaCategory.IMPORT_THIRD_COUNTRY)

    defects = decompose_invoice(invoice).defects

    assert InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND not in defects


def test_the_impossible_side_guidance_does_not_repeat_the_undeclared_advice() -> None:
    """The two members must not resolve to the same sentence.

    The whole reason for the split is that the remediation differs; identical
    guidance would make the extra member cosmetic.
    """
    impossible = INVOICE_DECOMPOSITION_DEFECT_GUIDANCE[InvoiceDecompositionDefect.CATEGORY_IMPOSSIBLE_ON_THIS_KIND]
    undeclared = INVOICE_DECOMPOSITION_DEFECT_GUIDANCE[InvoiceDecompositionDefect.IVA_TREATMENT_UNDECLARED]
    assert impossible != undeclared
