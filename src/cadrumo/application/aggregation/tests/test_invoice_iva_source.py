"""The invoice is the IVA source and the movement paying it is payment evidence.

LIVA art. 75 accrues IVA on the operation and art. 97 with RIVA art. 99 makes
the factura the document that grants a deduction, so every invoice accruing in
the period contributes and the movement an invoice names contributes no IVA of
its own. These tests pin the bounds of that rule through the one shared check
calculation and ledger readiness both run.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import governed_facts_in_scope
from ....domain.invoices.models import Invoice
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import InvoiceKind
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue
from ..invoice_iva_source import (
    InvoiceIvaFinding,
    InvoiceIvaFindingReason,
    period_invoice_iva_findings,
    period_invoice_iva_side,
)
from .ledger_source_mesh_support import (
    BUCKET_ID,
    domestic_iva_invoice,
    machine_acquisition_transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_QUARTER = Period.from_year_and_code(2025, "2T")
#: Fact 0032, LIVA art. 108.Dos.5.º: a good is a bien de inversión unless its value "sea inferior a" this.
_ESCASO_VALOR = Decimal("3005.06")


def _operation() -> PinnedAuthorityOperation:
    scoped = governed_facts_in_scope()
    assert isinstance(scoped, PinnedAuthorityOperation)
    return scoped


def _movement(provider_id: str, *, figures: bool = False) -> Transaction:
    """An outgoing business payment, with or without IVA figures of its own."""
    movement = machine_acquisition_transaction("material_oficina", provider_id=provider_id)
    if figures:
        return movement
    return movement.model_copy(update={"taxable_base": None, "iva_rate": None, "iva_amount": None})


def _received(number: str, *, base: Decimal, paid_by: tuple[Transaction, ...] = ()) -> Invoice:
    return domestic_iva_invoice(
        number,
        kind=InvoiceKind.RECEIVED,
        issued_at=date(2025, 4, 5),
        taxable_base=base,
        iva_amount=(base * Decimal("0.21")).quantize(Decimal("0.01")),
        linked_transaction_ids=tuple(movement.transaction_id for movement in paid_by),
    )


def _side(invoices: tuple[Invoice, ...], movements: tuple[Transaction, ...]):
    window = TransactionCatalogue.from_transactions(movements)
    return period_invoice_iva_side(
        invoices,
        bucket_id=BUCKET_ID,
        period=_QUARTER,
        window=window,
        repository=HeldTransactionCatalogue(window),
        operation=_operation(),
    )


def test_a_paying_movement_contributes_no_iva_and_its_invoice_does() -> None:
    paid = _movement("paid")
    unlinked = _movement("unlinked")
    invoice = _received("R-1", base=Decimal("100.00"), paid_by=(paid,))

    side = _side((invoice,), (paid, unlinked))

    assert side.payments.paid_transaction_ids == frozenset({paid.transaction_id})
    assert {movement.transaction_id for movement in side.unpaid_window} == {unlinked.transaction_id}
    assert [observation.ledger_id for observation in side.source.observations] == [f"invoice:{invoice.invoice_id}:0"]
    assert side.source.findings == ()


def test_an_unpaid_invoice_accruing_in_the_period_still_declares() -> None:
    """Art. 75 accrual does not wait for the payment."""
    invoice = _received("R-2", base=Decimal("100.00"))

    side = _side((invoice,), ())

    assert side.source.screen.invoice_ids == (invoice.invoice_id,)


def test_a_line_below_the_escaso_valor_threshold_is_its_own_current_deduction() -> None:
    invoice = _received("R-3", base=_ESCASO_VALOR - Decimal("0.01"))

    (observation,) = _side((invoice,), ()).source.observations

    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")
    assert observation.deduction_provenance is not None
    assert observation.deduction_provenance.authority == IvaDeductionEvidenceAuthority.from_registry("invoice_evidence")
    assert observation.deduction_provenance.source_locator == f"invoice:{invoice.invoice_id}"


def test_a_line_at_the_threshold_needs_the_person_to_say_what_it_is() -> None:
    """ "Sea inferior a" is strict: at exactly the threshold the good may be a bien de inversión."""
    invoice = _received("R-4", base=_ESCASO_VALOR)

    side = _side((invoice,), ())

    assert side.source.observations == ()
    assert side.source.findings == (
        InvoiceIvaFinding(reason=InvoiceIvaFindingReason.DEDUCTION_FAMILY_UNRESOLVED, invoice_id=invoice.invoice_id),
    )


def test_a_classified_paying_movement_grounds_an_invoice_above_the_threshold() -> None:
    classified = _movement("classified").model_copy(
        update={
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator="invoice:reviewed",
                evidence_digest="c" * 64,
            ),
        }
    )
    invoice = _received("R-5", base=Decimal("4000.00"), paid_by=(classified,))

    (observation,) = _side((invoice,), (classified,)).source.observations

    assert observation.deduction_fact_kind == IvaDeductionFactKind.from_registry("domestic_current")
    assert observation.deduction_provenance == classified.deduction_provenance


def test_a_bien_de_inversion_movement_stays_the_carrier_for_its_register() -> None:
    """The register pairs each record with the acquisition movement, so that movement keeps its observation."""
    acquisition = _movement("acquisition", figures=True).model_copy(
        update={"deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_investment")}
    )
    invoice = _received("R-6", base=Decimal("4000.00"), paid_by=(acquisition,))

    side = _side((invoice,), (acquisition,))

    assert side.payments.source_invoices == ()
    assert side.payments.paid_transaction_ids == frozenset()
    assert [movement.transaction_id for movement in side.unpaid_window] == [acquisition.transaction_id]


def test_a_paying_movement_whose_own_figures_disagree_is_reported() -> None:
    own = _movement("own-figures", figures=True)  # base 1000, cuota 210
    agreeing = _received("R-7", base=Decimal("1000.00"), paid_by=(own,))
    other = _movement("other-figures", figures=True)
    disagreeing = _received("R-8", base=Decimal("900.00"), paid_by=(other,))

    side = _side((agreeing, disagreeing), (own, other))

    assert side.contradicted == (disagreeing,)


def test_an_unlinked_movement_with_figures_that_pairs_an_invoice_is_a_double_count() -> None:
    figured = _movement("figured", figures=True)
    invoice = _received("R-9", base=Decimal("1000.00"))

    findings = _side((invoice,), (figured,)).source.findings

    assert (
        InvoiceIvaFinding(
            reason=InvoiceIvaFindingReason.MOVEMENT_DOUBLE_COUNT,
            invoice_id=invoice.invoice_id,
            transaction_id=figured.transaction_id,
        )
        in findings
    )


def test_an_unlinked_movement_without_figures_is_no_double_count() -> None:
    bare = _movement("bare")
    invoice = _received("R-10", base=Decimal("1000.00"))

    findings = _side((invoice,), (bare,)).source.findings

    assert all(finding.reason is not InvoiceIvaFindingReason.MOVEMENT_DOUBLE_COUNT for finding in findings)


@pytest.mark.parametrize(
    ("enrolled", "invoice_ids", "blocked"),
    [(True, ("a" * 64,), True), (True, (), False), (False, ("a" * 64,), False)],
)
def test_the_criterio_de_caja_blocks_only_a_period_with_invoices(
    enrolled: bool, invoice_ids: tuple[str, ...], blocked: bool
) -> None:
    findings = period_invoice_iva_findings((), invoice_ids=invoice_ids, cash_accounting_enrolled=enrolled)

    assert (InvoiceIvaFinding(reason=InvoiceIvaFindingReason.CASH_ACCOUNTING_UNMODELLED) in findings) is blocked


def test_a_link_held_on_the_movement_alone_still_makes_it_payment_evidence() -> None:
    """A record written before both sides were kept together cannot count the operation twice."""
    figured = _movement("one-way", figures=True)
    invoice = _received("R-11", base=Decimal("1000.00"))
    figured = figured.model_copy(update={"invoice_id": invoice.invoice_id})

    side = _side((invoice,), (figured,))

    assert side.payments.paid_transaction_ids == frozenset({figured.transaction_id})
    assert tuple(side.unpaid_window) == ()
    assert [observation.ledger_id for observation in side.source.observations] == [f"invoice:{invoice.invoice_id}:0"]
    assert side.source.findings == ()
