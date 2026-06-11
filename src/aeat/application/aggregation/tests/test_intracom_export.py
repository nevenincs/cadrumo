"""Persona test: Marc — intracom goods supply vs DOMESTIC_NOT_SUBJECT services.

Scenario (cross-border contract):
  Marc sells both physical goods and IT-consultancy services to a German
  GmbH (counterparty EU member state: 'de').

  - Goods invoice: INTRA_COMMUNITY_SUPPLY, counterparty_eu_member_state=de,
    iva_rate=0, iva_amount=0, taxable_base=5000.  Expected: casilla 59 += 5000.
  - Services invoice: DOMESTIC_NOT_SUBJECT (R12 — place-of-supply is Germany
    under Ley 37/1992 art. 69), iva_rate=0, iva_amount=0.  Expected: casilla 59
    remains 0; the R12 row flows through the pipeline as a zero-IVA observation
    with category=DOMESTIC_NOT_SUBJECT.
  - D5 gate: an INTRA_COMMUNITY_SUPPLY row with counterparty_eu_member_state=es
    is rejected as DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION.
  - D5 gate: an EXPORT_THIRD_COUNTRY_ZERO_RATED row with a non-None
    eu_member_state is rejected as EU_MEMBER_STATE_ON_EXPORT_TRANSACTION.
  - D5 gate: an INTRA_COMMUNITY_SUPPLY row with no eu_member_state is rejected
    as MISSING_COUNTERPARTY_EU_MEMBER_STATE.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core import Period
from ....domain.iva import EUMemberState, IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from .. import IvaLedgerAggregationIssueReason, aggregate_iva_ledger_observations
from .._iva_ledger import casilla_59_base_imponible, casilla_60_base_imponible

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_PERIOD = _period(2026, "2T")
_DE = EUMemberState.DE
_ES = EUMemberState.ES


def _raw(provider_id: str, *, amount: Decimal, direction: TransactionDirection) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=date(2026, 4, 15),
        value_date=date(2026, 4, 15),
        amount=amount,
        currency="EUR",
        counterparty="GmbH Berlin",
        description=f"Marc persona {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 16, 9, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _inbound_tx(
    provider_id: str,
    *,
    amount: Decimal,
    direction: TransactionDirection = TransactionDirection.INCOMING,
    taxable_base: Decimal,
    iva_rate: Decimal = Decimal("0"),
    iva_amount: Decimal = Decimal("0"),
    iva_category: IvaCategory | None = None,
    counterparty_eu_member_state: EUMemberState | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, amount=amount, direction=direction),
            "direction": direction,
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "counterparty_eu_member_state": counterparty_eu_member_state,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
        },
    )


def test_intracom_goods_supply_populates_casilla_59() -> None:
    """An INTRA_COMMUNITY_SUPPLY row with a non-ES member state feeds casilla 59."""
    tx = _inbound_tx(
        "goods-de-01",
        amount=Decimal("5000.00"),
        taxable_base=Decimal("5000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_eu_member_state=_DE,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert len(aggregation.observations) == 1
    obs = aggregation.observations[0]
    assert obs.category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert casilla_59_base_imponible(aggregation) == Decimal("5000.00")
    assert casilla_60_base_imponible(aggregation) == Decimal("0")


def test_domestic_not_subject_services_do_not_populate_casilla_59() -> None:
    """A DOMESTIC_NOT_SUBJECT (R12) services row does NOT feed casilla 59.

    Per cross-border contract D4: B2B services to EU taxable persons under art. 69 land in
    DOMESTIC_NOT_SUBJECT, not INTRA_COMMUNITY_SUPPLY.  The observation is
    produced (category=DOMESTIC_NOT_SUBJECT) but casilla_59_base_imponible
    returns 0 for this observation.
    """
    tx = _inbound_tx(
        "services-r12-01",
        amount=Decimal("2000.00"),
        taxable_base=Decimal("2000.00"),
        iva_category=IvaCategory.DOMESTIC_NOT_SUBJECT,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert len(aggregation.observations) == 1
    obs = aggregation.observations[0]
    assert obs.category is IvaCategory.DOMESTIC_NOT_SUBJECT
    assert casilla_59_base_imponible(aggregation) == Decimal("0")


def test_export_third_country_populates_casilla_60() -> None:
    """An EXPORT_THIRD_COUNTRY_ZERO_RATED row with no eu_member_state feeds casilla 60."""
    tx = _inbound_tx(
        "export-us-01",
        amount=Decimal("3000.00"),
        taxable_base=Decimal("3000.00"),
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        counterparty_eu_member_state=None,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert casilla_60_base_imponible(aggregation) == Decimal("3000.00")
    assert casilla_59_base_imponible(aggregation) == Decimal("0")


def test_d5_intracom_with_es_counterparty_is_rejected() -> None:
    """INTRA_COMMUNITY_SUPPLY with Spain as counterparty is a gate failure (contract D5)."""
    tx = _inbound_tx(
        "intracom-es-01",
        amount=Decimal("1000.00"),
        taxable_base=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_eu_member_state=_ES,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.observations) == 0
    assert len(aggregation.issues) == 1
    issue = aggregation.issues[0]
    assert issue.reason is IvaLedgerAggregationIssueReason.DOMESTIC_COUNTERPARTY_ON_INTRA_COMMUNITY_TRANSACTION


def test_d5_intracom_without_counterparty_is_rejected() -> None:
    """INTRA_COMMUNITY_SUPPLY with no eu_member_state is a gate failure (contract D5)."""
    tx = _inbound_tx(
        "intracom-no-state-01",
        amount=Decimal("1000.00"),
        taxable_base=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_eu_member_state=None,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.observations) == 0
    assert len(aggregation.issues) == 1
    assert aggregation.issues[0].reason is IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_EU_MEMBER_STATE


def test_d5_export_with_eu_member_state_is_rejected() -> None:
    """EXPORT_THIRD_COUNTRY_ZERO_RATED with a non-None eu_member_state is rejected (contract D5)."""
    tx = _inbound_tx(
        "export-with-eu-01",
        amount=Decimal("800.00"),
        taxable_base=Decimal("800.00"),
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        counterparty_eu_member_state=_DE,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.observations) == 0
    assert len(aggregation.issues) == 1
    assert aggregation.issues[0].reason is IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION


def test_marc_combined_scenario() -> None:
    """Full Marc scenario: goods (casilla 59) + services R12 (no casilla 59)."""
    goods_tx = _inbound_tx(
        "marc-goods-de",
        amount=Decimal("5000.00"),
        taxable_base=Decimal("5000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_eu_member_state=_DE,
    )
    services_tx = _inbound_tx(
        "marc-services-r12",
        amount=Decimal("2000.00"),
        taxable_base=Decimal("2000.00"),
        iva_category=IvaCategory.DOMESTIC_NOT_SUBJECT,
    )
    catalogue = TransactionCatalogue.from_transactions([goods_tx, services_tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert len(aggregation.observations) == 2
    categories = {obs.category for obs in aggregation.observations}
    assert IvaCategory.INTRA_COMMUNITY_SUPPLY in categories
    assert IvaCategory.DOMESTIC_NOT_SUBJECT in categories
    # Only the goods invoice feeds casilla 59
    assert casilla_59_base_imponible(aggregation) == Decimal("5000.00")
    assert casilla_60_base_imponible(aggregation) == Decimal("0")
