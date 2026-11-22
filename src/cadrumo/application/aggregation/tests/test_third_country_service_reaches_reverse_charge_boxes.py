"""A service bought from a supplier outside the Community is self-assessed and deducted by the recipient.

LIVA art. 69.Uno.1.º places a B2B service where its recipient is established
"con independencia de dónde se encuentre establecido el prestador", and art.
84.Uno.2.º a) makes the Spanish recipient the sujeto pasivo when the supplier is
not established in the territorio de aplicación del Impuesto. The AEAT Modelo
303 instructions then declare that self-assessment in casillas 12 and 13
("cuotas devengadas ... por inversión del sujeto pasivo (artículo 84. Uno. 2.º
y 4.º)") and, when the service is a current expense, deduct the same cuota in
casillas 28 and 29 (operaciones interiores corrientes).

A synthetic US software subscription of 1000.00 at the general 21 % rate is
classified through the registry decision table and screened as a received
invoice: the period must self-assess 1000.00 / 210.00 and deduct 1000.00 /
210.00, every supported year.

Real-behaviour: the real decision table, invoice screen and binding resolver
over the published authority. No mocks, stubs, skips or xfail.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.invoices.enums import PaymentStatus, resolve_iva_rate_token
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.classification import (
    CustomerTaxStatus,
    IvaInvoiceClassificationCriteria,
    TransactionKind,
    classify_iva,
    resolve_iva_classification_inputs,
)
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.schema import InvoiceKind, IvaCategory, IvaTerritorialScope
from ....domain.transactions.models import Transaction
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values
from ..modelo_bindings_invoice_iva import ScreenedInvoiceIva, screened_invoice_iva_observations
from .ledger_source_mesh_support import machine_acquisition_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET_ID = "52525252-5252-4252-8252-525252525252"
_YEARS = tuple(filing_year_envelope().years)
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")

_SELF_ASSESSED_BASE = "modelo-303-iva-autorepercutido-interior-devengado-base"
_SELF_ASSESSED_CUOTA = "modelo-303-iva-autorepercutido-interior-devengado-cuota"
_DEDUCTED_BASE = "modelo-303-iva-autorepercutido-interior-deducible-base"
_DEDUCTED_CUOTA = "modelo-303-iva-autorepercutido-interior-deducible-cuota"


def _on(year: int) -> date:
    return date(year, 5, 12)


def _classified_category(year: int) -> IvaCategory:
    criteria = IvaInvoiceClassificationCriteria.model_validate(
        {
            "transaction_date": _on(year),
            "issuer_residency": IvaTerritorialScope.from_registry("third_country"),
            "customer_residency": IvaTerritorialScope.from_registry("es_mainland"),
            "customer_tax_status": CustomerTaxStatus.from_registry("b2b_iva_registered"),
            "kind": TransactionKind("services_general"),
            "direction": InvoiceKind.RECEIVED,
        }
    )
    with bundled_indexed_authority().operation() as operation:
        inputs = resolve_iva_classification_inputs(effective_date=criteria.transaction_date, operation=operation)
        result = classify_iva(
            criteria,
            rules=inputs.rules,
            rate_categories=inputs.rate_categories,
            rate_territories=inputs.rate_territories,
            operation=operation,
        )
    assert result.requires_reverse_charge is True
    return result.category


def _invoice(year: int, *, category: IvaCategory, linked: tuple[str, ...] = ()) -> Invoice:
    on = _on(year)
    line = InvoiceLine(
        description="Suscripción anual de software",
        quantity=Decimal("1"),
        unit_price=_BASE,
        subtotal=_BASE,
        iva_rate=resolve_iva_rate_token("RATE_21", on),
        iva_amount=_CUOTA,
    )
    return Invoice.model_validate(
        {
            "bucket_id": _BUCKET_ID,
            "kind": InvoiceKind.RECEIVED,
            "invoice_number": "INV-US-0042",
            "issued_at": on,
            "counterparty_name": "Example Software Inc.",
            "counterparty_tax_id": "US123456789",
            "counterparty_country": "US",
            "base_total": _BASE,
            "iva_total": _CUOTA,
            "grand_total": _BASE + _CUOTA,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": category,
            "linked_transaction_ids": linked,
        },
    )


def _paying_movement(year: int) -> Transaction:
    """The bank payment, classified as a current deduction by the operator."""
    return machine_acquisition_transaction("software", provider_id="us-saas-payment").model_copy(
        update={
            "taxable_base": None,
            "iva_rate": None,
            "iva_amount": None,
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_current"),
            "deduction_provenance": IvaDeductionClassificationProvenance(
                authority=IvaDeductionEvidenceAuthority.from_registry("invoice_evidence"),
                source_locator="transaction:us-saas-payment",
                evidence_digest="b" * 64,
            ),
        }
    )


def _screen(invoice: Invoice, year: int, movements: tuple[Transaction, ...]) -> ScreenedInvoiceIva:
    with bundled_indexed_authority().operation() as operation:
        return screened_invoice_iva_observations(
            (invoice,),
            bucket_id=_BUCKET_ID,
            period=Period.from_year_and_code(year, "2T"),
            linked_movements={movement.transaction_id: movement for movement in movements},
            operation=operation,
        )


def _declared(screen: ScreenedInvoiceIva, year: int) -> dict[str, Decimal]:
    revision = published_snapshot("303", filing_year=year, period="2T").revision
    with bundled_indexed_authority().operation() as operation:
        resolved = resolve_iva_ledger_binding_values(revision, screen.observations, operation=operation)
    return {str(key): value for key, value in resolved.items() if value}


@pytest.mark.parametrize("year", _YEARS)
def test_the_decision_table_makes_the_recipient_the_sujeto_pasivo(year: int) -> None:
    assert _classified_category(year) == IvaCategory("domestic_reverse_charge")


@pytest.mark.parametrize("year", _YEARS)
def test_a_paid_us_subscription_is_self_assessed_and_deducted(year: int) -> None:
    movement = _paying_movement(year)
    invoice = _invoice(year, category=_classified_category(year), linked=(movement.transaction_id,))

    declared = _declared(_screen(invoice, year, (movement,)), year)

    assert declared.get(_SELF_ASSESSED_BASE) == _BASE, declared
    assert declared.get(_SELF_ASSESSED_CUOTA) == _CUOTA, declared
    assert declared.get(_DEDUCTED_BASE) == _BASE, declared
    assert declared.get(_DEDUCTED_CUOTA) == _CUOTA, declared


@pytest.mark.parametrize("year", _YEARS)
def test_the_self_assessment_and_deduction_net_to_zero(year: int) -> None:
    """Art. 84 self-assessment plus full art. 92 deduction leaves nothing to pay for the service."""
    movement = _paying_movement(year)
    invoice = _invoice(year, category=_classified_category(year), linked=(movement.transaction_id,))

    declared = _declared(_screen(invoice, year, (movement,)), year)

    assert declared[_SELF_ASSESSED_CUOTA] - declared[_DEDUCTED_CUOTA] == Decimal("0.00")


@pytest.mark.parametrize("year", _YEARS)
def test_an_unpaid_subscription_below_escaso_valor_is_grounded_by_the_invoice_itself(year: int) -> None:
    """With no bank link yet, a line below the art. 108 threshold is a current deduction the factura grounds."""
    invoice = _invoice(year, category=_classified_category(year))

    declared = _declared(_screen(invoice, year, ()), year)

    assert declared.get(_SELF_ASSESSED_BASE) == _BASE, declared
    assert declared.get(_SELF_ASSESSED_CUOTA) == _CUOTA, declared
    assert declared.get(_DEDUCTED_BASE) == _BASE, declared
    assert declared.get(_DEDUCTED_CUOTA) == _CUOTA, declared
