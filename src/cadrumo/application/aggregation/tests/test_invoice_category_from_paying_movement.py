"""An invoice that states no IVA category is classified by its paying movements, or its base stays unrouted.

The invoice is the IVA source and the movement that pays it only the payment
evidence. A sale imported from the Libro de facturas carries a base, a rate and
a counterparty but no IVA category. A business-to-business service to a German
customer is invoiced at 0 % because LIVA art. 69.Uno.1 places it in Germany, and
Modelo 303 declares its base in box 59. Read from the rate slot alone, its line
became a domestic zero-rated operation, a category no Modelo 303 base box
selects, so the 303 refused verification on an unrouted base it never named.

The operator had already classified the operation on the movement that paid
it. These tests run the real invoice screen, the real binding resolver and the
real quantity screen over the published Modelo 303 2025 1T revision:

* the category the paying movements agree on classifies the invoice, so its
  base reaches box 59 and nothing is left unrouted;
* the IRPF retención a Spanish customer withholds is no IVA quantity, so it
  neither blocks Modelo 303 nor reaches any of its boxes;
* without a classified movement the 0 % base is still unrouted and still
  named, row by row, because it is a Modelo 303 quantity no box draws;
* movements that disagree ground no category, and a category the invoice
  states itself governs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ledger_iva_bindings import (
    IvaLedgerObservation,
    unrouted_ledger_iva_quantities,
)
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.invoices.models import Invoice
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...invoices.catalogue_creation import build_catalogue_invoice
from ...invoices.tests.catalogue_creation_fakes import in_memory_catalogue_creation_ports
from ...ledger.preflight import HeldTransactionCatalogue
from ..invoice_iva_source import period_invoice_iva_side
from ..iva_ledger_apportionment import resolve_iva_ledger_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"
_Q1_2025 = Period.from_year_and_code(2025, "1T")
_CASILLA_07 = "modelo-303-iva-repercutido-general-base"
_CASILLA_59 = "modelo-303-casilla-59-entregas-intracomunitarias-base"
_SERVICE_BASE = Decimal("1500.00")
_SERVICE = IvaCategory("intra_community_service_supply")
_NOW = datetime(2025, 2, 1, 9, 0, tzinfo=UTC)


def _issued(
    number: str,
    *,
    on: date,
    nif: str,
    name: str,
    country: str,
    base: str,
    rate: str,
    retention: tuple[str, str] | None,
    operation: PinnedAuthorityOperation,
) -> Invoice:
    """An issued invoice built exactly as a Libro de facturas row import builds it: no IVA category."""
    return build_catalogue_invoice(
        bucket_id=_BUCKET_ID,
        kind=InvoiceKind.ISSUED,
        counterparty_name=name,
        counterparty_tax_id=nif,
        counterparty_country=country,
        invoice_number=number,
        issued_at=on,
        currency="EUR",
        taxable_base=Decimal(base),
        iva_rate=Decimal(rate),
        retention_rate=None if retention is None else Decimal(retention[0]),
        retention_amount=None if retention is None else Decimal(retention[1]),
        rate_provider=in_memory_catalogue_creation_ports().rate_provider,
        operation=operation,
    )


def _eu_service(operation: PinnedAuthorityOperation) -> Invoice:
    return _issued(
        "2025-002",
        on=date(2025, 1, 31),
        nif="DE123456788",
        name="Kunde GmbH",
        country="DE",
        base=format(_SERVICE_BASE, "f"),
        rate="0",
        retention=None,
        operation=operation,
    )


def _withheld_domestic_sale(operation: PinnedAuthorityOperation) -> Invoice:
    """A 21 % sale to a Spanish company that withholds 15 % IRPF on the professional's fee."""
    return _issued(
        "2025-001",
        on=date(2025, 1, 15),
        nif="B81000010",
        name="Alfa SL",
        country="ES",
        base="2000.00",
        rate="21",
        retention=("0.15", "300.00"),
        operation=operation,
    )


def _collection(provider_id: str, *, category: IvaCategory | None, amount: Decimal = _SERVICE_BASE) -> Transaction:
    """A bank collection of the German service, as the operator classified it."""
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2025, 2, 3),
        value_date=date(2025, 2, 3),
        amount=amount,
        currency="EUR",
        counterparty="Kunde GmbH",
        description=f"cobro {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=_NOW,
            provider_name="manual",
        ),
        raw_fields={"row": provider_id},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": amount,
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": category,
            "counterparty_country": "DE",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": _NOW,
            "classified_by": "manual",
        },
    )


def _paid_by(invoice: Invoice, *movements: Transaction) -> Invoice:
    return invoice.model_copy(
        update={"linked_transaction_ids": tuple(movement.transaction_id for movement in movements)}
    )


def _observations(
    invoices: tuple[Invoice, ...],
    movements: tuple[Transaction, ...],
    operation: PinnedAuthorityOperation,
) -> tuple[IvaLedgerObservation, ...]:
    """The period's IVA observations, through the invoice side calculation and readiness share."""
    window = TransactionCatalogue.from_transactions(movements)
    side = period_invoice_iva_side(
        invoices,
        bucket_id=_BUCKET_ID,
        period=_Q1_2025,
        window=window,
        repository=HeldTransactionCatalogue(window),
        operation=operation,
    )
    assert side.contradicted == ()
    return side.source.observations


def _revision(operation: PinnedAuthorityOperation) -> ModeloRevision:
    return operation.snapshot("303", filing_year=2025, period="1T").revision


def _resolved(
    revision: ModeloRevision, observations: tuple[IvaLedgerObservation, ...], operation: PinnedAuthorityOperation
) -> dict[str, Decimal]:
    return {
        str(binding_id): value
        for binding_id, value in resolve_iva_ledger_binding_values(revision, observations, operation=operation).items()
    }


def test_the_paying_movements_category_puts_the_eu_service_base_in_box_59(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The movement's classification of the same operation reaches the invoice, and the base reaches box 59."""
    collection = _collection("kunde-1", category=_SERVICE)
    invoice = _paid_by(_eu_service(authority_operation), collection)
    assert invoice.iva_category is None, "the imported invoice states no category of its own"

    observations = _observations((invoice,), (collection,), authority_operation)
    revision = _revision(authority_operation)

    (observation,) = observations
    assert observation.category == _SERVICE
    assert observation.base_amount == _SERVICE_BASE
    assert _resolved(revision, observations, authority_operation)[_CASILLA_59] == _SERVICE_BASE
    assert unrouted_ledger_iva_quantities(revision, observations) == ()


def test_an_issued_invoices_irpf_retencion_neither_blocks_nor_reaches_modelo_303(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A retención is IRPF, settled outside the invoice total, and no IVA quantity of the 303.

    The sale's base and cuota reach boxes 07 and 09; the 300.00 withheld leaves
    no unrouted quantity and adds nothing to any box.
    """
    sale = _withheld_domestic_sale(authority_operation)
    assert sale.retention_amount == Decimal("300.00")
    revision = _revision(authority_operation)

    observations = _observations((sale,), (), authority_operation)
    resolved = _resolved(revision, observations, authority_operation)

    assert unrouted_ledger_iva_quantities(revision, observations) == ()
    assert resolved[_CASILLA_07] == Decimal("2000.00")
    assert {value for value in resolved.values() if value} == {Decimal("2000.00"), Decimal("420.00")}


def test_without_a_classified_movement_the_zero_rated_base_stays_unrouted_and_named(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """A genuine Modelo 303 base no box draws still blocks, and the screen names its row and amount."""
    invoice = _eu_service(authority_operation)
    revision = _revision(authority_operation)

    observations = _observations((invoice,), (), authority_operation)

    (unrouted,) = unrouted_ledger_iva_quantities(revision, observations)
    assert unrouted.fact == "base_amount_sum"
    assert unrouted.total == _SERVICE_BASE
    assert [row.ledger_id for row in unrouted.observations] == [f"invoice:{invoice.invoice_id}:0"]
    assert _resolved(revision, observations, authority_operation).get(_CASILLA_59, Decimal("0")) == Decimal("0")


def test_movements_that_disagree_ground_no_category(authority_operation: PinnedAuthorityOperation) -> None:
    """One payment classified as an EU service and one left domestic: no choice is made between them."""
    half = Decimal("750.00")
    movements = (
        _collection("kunde-1", category=_SERVICE, amount=half),
        _collection("kunde-2", category=None, amount=half),
    )
    invoice = _paid_by(_eu_service(authority_operation), *movements)
    revision = _revision(authority_operation)

    observations = _observations((invoice,), movements, authority_operation)

    (unrouted,) = unrouted_ledger_iva_quantities(revision, observations)
    assert unrouted.total == _SERVICE_BASE


def test_a_category_the_invoice_states_governs_its_paying_movement(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The invoice's own declaration is never replaced by a movement's classification."""
    collection = _collection("kunde-1", category=IvaCategory("operacion_no_sujeta"))
    invoice = _paid_by(_eu_service(authority_operation), collection).model_copy(update={"iva_category": _SERVICE})

    observations = _observations((invoice,), (collection,), authority_operation)

    (observation,) = observations
    assert observation.category == _SERVICE
    assert _resolved(_revision(authority_operation), observations, authority_operation)[_CASILLA_59] == _SERVICE_BASE
