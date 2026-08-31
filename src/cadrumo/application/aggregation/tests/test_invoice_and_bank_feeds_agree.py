"""One operation, expressed both ways, must reach the same casilla.

Two feeds populate the ``ledger_iva_aggregation`` binding source: the
bank-transaction ledger and the invoice catalogue. Nothing compared them, and
that is the hole an intra-community supply expressed as an invoice lived in for
as long as it did.

Casilla 59 was not untested. It was tested from ONE side: a transaction-shaped
intra-community supply reached it and the assertion passed, so the casilla read
as guarded. An invoice-shaped one never arrived, and no test existed that could
have noticed, because no test drove the invoice feed to a casilla at all.

The transport axis already has a gate -- the pull path and the calculate path are
held to the same casilla values. That axis is about two ways of REACHING one
resolver. This is the other axis: two SOURCES populating one binding, which can
diverge while every transport of each stays perfectly self-consistent. A feed
that silently declares less than its sibling is invisible to a per-feed test by
construction, since each feed's tests only ever assert what that feed produces.

So the gate is a comparison, not an expectation. Neither side is asserted against
a hand-written figure that could be updated to match a regression; each is
asserted against the OTHER, and against the operation both are meant to describe.

The operation is chosen so its two representations must agree exactly. An
intra-community supply of goods for a stated base with no cuota carries the same
declarable facts however it was recorded, so any difference between the feeds is
a defect rather than a modelling choice needing interpretation.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.invoices.enums import IvaRate
from ....domain.invoices.models import Invoice
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import EUMemberState, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .._iva_ledger import resolve_iva_ledger_binding_values
from .._modelo_bindings_invoice_iva import _invoice_line_iva_observation
from ._iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BASE = Decimal("5000.00")
_DAY = date(2026, 4, 15)
_PERIOD = Period.from_year_and_code(2026, "2T")

_CASILLA_59 = "modelo-303-casilla-59-entregas-intracomunitarias-base"
_CASILLA_60 = "modelo-303-casilla-60-exportaciones-base"


@cache
def _revision():
    return bundled_authority().snapshot("303", filing_year=2026, period="2T").revision


def _resolved(observations) -> dict[str, Decimal]:
    return {str(k): v for k, v in resolve_iva_ledger_binding_values(_revision(), tuple(observations)).items()}


def _country_of(member_state: EUMemberState | None) -> str | None:
    """Return the alpha-2 code a Member State names, for the establishment axis."""
    return member_state.value.upper() if member_state is not None else None


def _as_bank_transaction(
    *,
    category: IvaCategory,
    member_state: EUMemberState | None,
    country: str | None = None,
) -> Transaction:
    """The operation as the bank feed records it."""
    raw = RawTransaction(
        provider_transaction_id="feed-parity-01",
        booked_date=_DAY,
        value_date=_DAY,
        amount=_BASE,
        currency="EUR",
        counterparty="GmbH Berlin",
        description="one operation, two feeds",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _BASE,
            "iva_rate": Decimal("0"),
            "iva_amount": Decimal("0"),
            "iva_category": category,
            "counterparty_country": (country if country is not None else _country_of(member_state)),
            # Where the acquirer is established and where it is IVA-identified
            # agree in this scenario. They are still supplied separately: the
            # art. 25 gate reads only the second, and the parity this module
            # asserts is that BOTH feeds read the same one.
            "counterparty_identification_state": member_state,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        },
    )


def _as_invoice(*, category: IvaCategory, country: str, tax_id: str) -> Invoice:
    """The same operation as the invoice feed records it."""
    return Invoice.model_validate(
        {
            "bucket_id": "29292929-2929-4929-8929-292929292929",
            "kind": InvoiceKind.ISSUED.value,
            "invoice_number": "F-2026-0101",
            "issued_at": _DAY.isoformat(),
            "counterparty_name": "GmbH Berlin",
            "counterparty_tax_id": tax_id,
            "counterparty_country": country,
            "counterparty_identification_state": country.lower() if country != "US" else None,
            "base_total": format(_BASE, "f"),
            "iva_total": "0.00",
            "grand_total": format(_BASE, "f"),
            "currency": "EUR",
            "payment_status": "PENDING",
            "iva_category": category.value,
            "lines": [
                {
                    "description": "Entrega de bienes",
                    "quantity": "1",
                    "unit_price": format(_BASE, "f"),
                    "subtotal": format(_BASE, "f"),
                    "iva_rate": IvaRate.EXEMPT.value,
                    "iva_amount": "0.00",
                },
            ],
        },
    )


def _bank_side(*, category: IvaCategory, member_state: EUMemberState | None, country: str | None = None):
    aggregation = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions(
            [_as_bank_transaction(category=category, member_state=member_state, country=country)],
        ),
        period=_PERIOD,
    )
    assert not aggregation.issues, f"the bank feed refused the operation: {aggregation.issues}"
    return aggregation.observations


def _invoice_side(*, category: IvaCategory, country: str, tax_id: str):
    invoice = _as_invoice(category=category, country=country, tax_id=tax_id)
    line = invoice.lines[0]
    base_amount_eur = invoice.line_amount_eur(line.subtotal)
    iva_amount_eur = invoice.line_amount_eur(line.iva_amount)
    assert base_amount_eur is not None
    assert iva_amount_eur is not None
    observation = _invoice_line_iva_observation(
        invoice=invoice,
        line=line,
        line_index=0,
        devengo_date=_DAY,
        recargo_amount=Decimal("0"),
        base_amount_eur=base_amount_eur,
        iva_amount_eur=iva_amount_eur,
    )
    assert observation is not None, "the invoice feed produced no observation for a declarable operation"
    return (observation,)


def test_both_feeds_declare_an_intra_community_supply_into_casilla_59() -> None:
    """The casilla is reached from both sides, with the same figure.

    Asserted as a comparison between the feeds rather than each against a
    constant, so the gate cannot be satisfied by updating an expectation to
    match a regression. The shared figure is then checked against the base the
    operation actually carries, so the two agreeing on a wrong number fails too.
    """
    bank = _resolved(_bank_side(category=IvaCategory.INTRA_COMMUNITY_SUPPLY, member_state=EUMemberState.DE))
    invoice = _resolved(
        _invoice_side(category=IvaCategory.INTRA_COMMUNITY_SUPPLY, country="DE", tax_id="DE811907980"),
    )

    assert invoice.get(_CASILLA_59) == bank.get(_CASILLA_59), (
        f"the two feeds disagree on casilla 59: invoice={invoice.get(_CASILLA_59)!r} bank={bank.get(_CASILLA_59)!r}"
    )
    assert bank.get(_CASILLA_59) == _BASE, "both feeds agree, and both are wrong about the operation's base"


def test_both_feeds_declare_an_export_into_casilla_60() -> None:
    """The second casilla, so a routing that sent everything to one is caught.

    A feed that collapsed every exempt base into casilla 59 would satisfy the
    intra-community comparison above on its own.
    """
    bank = _resolved(
        _bank_side(category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, member_state=None, country="US"),
    )
    invoice = _resolved(
        _invoice_side(category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED, country="US", tax_id="US987654321"),
    )

    assert invoice.get(_CASILLA_60) == bank.get(_CASILLA_60), (
        f"the two feeds disagree on casilla 60: invoice={invoice.get(_CASILLA_60)!r} bank={bank.get(_CASILLA_60)!r}"
    )
    assert bank.get(_CASILLA_60) == _BASE
    assert not invoice.get(_CASILLA_59), "an export must not also land in the intra-community casilla"


def test_the_two_feeds_classify_the_operation_identically() -> None:
    """The observation itself agrees, not only the figure it happens to reach.

    Kept alongside the casilla assertions because the two are separate failures:
    an observation can classify correctly and still match no binding selector,
    which is exactly what the first attempt at this fix produced. Asserting only
    the casilla would miss a category that drifted while still resolving;
    asserting only the category would miss a selector that stopped matching.
    """
    (bank,) = _bank_side(category=IvaCategory.INTRA_COMMUNITY_SUPPLY, member_state=EUMemberState.DE)
    (invoice,) = _invoice_side(category=IvaCategory.INTRA_COMMUNITY_SUPPLY, country="DE", tax_id="DE811907980")

    assert invoice.category is bank.category
    assert invoice.rate_kind is bank.rate_kind
    assert invoice.flow_direction is bank.flow_direction
    assert invoice.base_amount == bank.base_amount
    assert invoice.iva_amount == bank.iva_amount
