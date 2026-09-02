"""A 0 % row carrying a non-zero cuota is refused at ingest, not routed onward.

Cuota is base x tipo, so a row declaring a zero tipo admits only a zero cuota.
A row asserting both is not an unrouted value needing a home -- it is corrupt
data, and the two facts it carries contradict each other. Routing it would put
money into an official 0 % box that AEAT can disprove from the filed record
alone, because the return publishes the rate and the cuota side by side.

This closes the live half of the Modelo 390 zero-tier finding. The other half of
that finding -- a zero row whose rate was never recorded dropping its cuota --
is NOT reachable through this path and needs no fix here: the classifier already
refuses a rate-less row with ``missing_iva_rate``, which the first test below
pins as the control that keeps this refusal correctly scoped. That distinction
was only visible by driving the real classifier; fed straight to the resolver, a
hand-built rate-less observation does drop, which measures the selector rather
than anything a taxpayer can reach.

Real-behaviour: real :class:`Transaction` rows through the real
``aggregate_iva_ledger_observations`` classifier. ``applied_rate`` and the
category are DECIDED by the classifier from the row's own facts rather than set
here, which is what makes the refusal a statement about the production path. No
mocks, stubs, skips or xfail.

Non-tautology: the legitimate zero row and the corrupt row differ in exactly one
field, so a refusal keyed on anything but that field fails one of the two tests.
The corrupt row's cuota is distinct from its base, so a check that confused the
two would not land on the expected refusal.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.period import Period
from ....domain.calculations.registry.ledger_iva_bindings import IvaLedgerObservation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..iva_ledger import IvaLedgerAggregationIssueReason
from .iva_authority_support import aggregate_iva_ledger_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_PERIOD = Period.from_year_and_code(2024, "4T")
_ON = date(2024, 11, 6)
_BASE = Decimal("1000.00")
#: Distinct from the base, so a check that confused cuota with base misses it.
_CUOTA = Decimal("99.00")


def _transaction(row_id: str, *, iva_rate: Decimal | None, iva_amount: Decimal) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=row_id,
                booked_date=_ON,
                value_date=_ON,
                amount=_BASE + iva_amount,
                currency="EUR",
                counterparty="Cliente",
                description=f"venta {row_id}",
                provenance=RawProvenance(
                    source_path=Path("ledger.csv"),
                    source_sha256="d" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime(2024, 12, 1, 12, 0, tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "taxable_base": _BASE,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": None,
            "exemption_article": None,
            "art_104_tres_exclusion": None,
            "prorrata_reference": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "fx_rate": None,
            "value_in_eur": None,
            "classified_at": datetime(2024, 12, 2, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregate(transaction: Transaction) -> tuple[Sequence[IvaLedgerObservation], list[str]]:
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)
    return aggregation.observations, [issue.reason.value for issue in aggregation.issues]


def test_a_rate_less_row_is_already_refused_and_never_reaches_the_zero_tier() -> None:
    """Control, and the reason this refusal does not need to cover the drop case.

    The zero-tier finding was recorded as a dropped cuota on a row whose rate
    was never captured. That drop is real at the resolver but unreachable here:
    the classifier refuses a rate-less row outright. Pinning it keeps the
    refusal below correctly scoped -- if this ever stops refusing, a rate-less
    row starts reaching the zero tier and the drop becomes live.
    """
    observations, reasons = _aggregate(_transaction("row-no-rate", iva_rate=None, iva_amount=_CUOTA))
    assert observations == ()
    assert reasons == [IvaLedgerAggregationIssueReason.MISSING_IVA_RATE.value]


def test_a_zero_rated_row_carrying_a_cuota_is_refused() -> None:
    """The live defect: 0 % plus a non-zero cuota is arithmetically impossible."""
    observations, reasons = _aggregate(_transaction("row-zero-with-cuota", iva_rate=Decimal("0"), iva_amount=_CUOTA))
    assert observations == (), "a self-contradicting zero-rated row produced an observation instead of being refused"
    assert reasons == [IvaLedgerAggregationIssueReason.CUOTA_ON_ZERO_RATED_ROW.value]


def test_the_refusal_names_both_contradicting_facts() -> None:
    """The operator has to repair one of two facts, so the issue must name both.

    A refusal saying only "invalid row" sends the operator looking; the rate and
    the amount together are what identify the contradiction.
    """
    transaction = _transaction("row-detail", iva_rate=Decimal("0"), iva_amount=_CUOTA)
    catalogue = TransactionCatalogue.model_validate({"transactions": {transaction.transaction_id: transaction}})
    detail = aggregate_iva_ledger_observations(catalogue, period=_PERIOD).issues[0].detail
    assert "iva_rate 0" in detail
    assert str(_CUOTA) in detail


def test_a_legitimate_zero_rated_row_still_produces_its_observation() -> None:
    """Positive control: the refusal must not swallow the ordinary zero row.

    Differs from the refused row in exactly one field, so a refusal keyed on
    anything broader than the contradiction -- the category, the zero rate
    alone, or a zero base -- fails here rather than silently deleting every
    legitimate zero-rated supply from the return.
    """
    observations, reasons = _aggregate(_transaction("row-zero-clean", iva_rate=Decimal("0"), iva_amount=Decimal("0")))
    assert reasons == []
    assert len(observations) == 1
    observation = observations[0]
    assert observation.iva_amount == Decimal("0")
    assert observation.base_amount == _BASE, "the legitimate zero row lost its base imponible"


def test_a_rated_row_carrying_its_cuota_is_untouched() -> None:
    """Second positive control: the refusal is scoped to the ZERO rate.

    A 21 % row carries a non-zero cuota legitimately, so a check that fired on
    "row has a cuota" rather than "row has a cuota at a zero tipo" would delete
    ordinary sales. This is the mutation that guard would not survive.
    """
    observations, reasons = _aggregate(
        _transaction("row-general", iva_rate=Decimal("0.21"), iva_amount=Decimal("210.00")),
    )
    assert reasons == []
    assert len(observations) == 1
    assert observations[0].iva_amount == Decimal("210.00")
