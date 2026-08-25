"""Persona test: Marc — intracom goods supply vs DOMESTIC_NOT_SUBJECT services.

Scenario (cross-border contract):
  Marc sells both physical goods and IT-consultancy services to a German
  GmbH (counterparty EU member state: 'de').

  - Goods invoice: INTRA_COMMUNITY_SUPPLY, counterparty_country=DE,
    iva_rate=0, iva_amount=0, taxable_base=5000.  Expected: casilla 59 += 5000.
  - Services invoice: DOMESTIC_NOT_SUBJECT (R12 — place-of-supply is Germany
    under Ley 37/1992 art. 69), iva_rate=0, iva_amount=0.  Expected: casilla 59
    remains 0; the R12 row flows through the pipeline as a zero-IVA observation
    with category=DOMESTIC_NOT_SUBJECT.
  - D5 gate: an INTRA_COMMUNITY_SUPPLY row whose counterparty is IVA-identified
    in Spain is rejected as
    DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION -- the acquirer's
    identification is what Ley 37/1992 art. 25 exempts on, not its address.
  - D5 gate: export and export-assimilated rows with a non-None eu_member_state
    are rejected as EU_MEMBER_STATE_ON_EXPORT_TRANSACTION. The export families
    genuinely turn on establishment: an export leaves the Union.
  - D5 gate: an INTRA_COMMUNITY_SUPPLY row with no identification state is
    rejected as MISSING_COUNTERPARTY_IDENTIFICATION_STATE, never resolved from
    the counterparty's country.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.ids import BindingId
from cadrumo.domain.calculations.registry.ledger_bindings import resolve_ledger_iva_aggregation_binding_values

from ....core import CasillaId, validated_casilla_id
from ....core.resources import resources
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
from .. import IvaLedgerAggregationIssueReason
from .._iva_ledger import IvaLedgerAggregation
from ._iva_authority_support import aggregate_iva_ledger_observations
from ._renta_income_aggregation_support import _period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Casilla 59/60 base imponible are resolved through the registry
# ledger_iva_aggregation bindings (the canonical path production uses), not a
# bespoke application-tier helper. These tests assert the registry binding
# reproduces the expected base sums end-to-end.
_CASILLA_BASE_BINDING: dict[CasillaId, BindingId] = {
    validated_casilla_id("59", surface="_CASILLA_BASE_BINDING.59"): (
        "modelo-303-casilla-59-entregas-intracomunitarias-base"
    ),
    validated_casilla_id("60", surface="_CASILLA_BASE_BINDING.60"): ("modelo-303-casilla-60-exportaciones-base"),
}


@cache
def _modelo_303_revision():
    return resources().modelos.authority.snapshot("303", filing_year=2025, period="1T").revision


def _casilla_base(aggregation: IvaLedgerAggregation, casilla_id: CasillaId) -> Decimal:
    """Resolve a casilla base imponible via the registry binding from an aggregation."""
    resolved = resolve_ledger_iva_aggregation_binding_values(_modelo_303_revision(), aggregation.observations)
    return resolved.get(_CASILLA_BASE_BINDING[casilla_id], Decimal("0"))


_PERIOD = _period(2026, "2T")
_DE = EUMemberState.DE
_ES = EUMemberState.ES
_XI = EUMemberState.XI


def _raw(provider_id: str, *, amount: Decimal, direction: TransactionDirection) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
    counterparty_country: str | None = None,
    counterparty_identification_state: EUMemberState | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id, amount=amount, direction=direction),
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "iva_category": iva_category,
            "counterparty_country": counterparty_country,
            "counterparty_identification_state": counterparty_identification_state,
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
        counterparty_country="DE",
        counterparty_identification_state=_DE,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert len(aggregation.observations) == 1
    obs = aggregation.observations[0]
    assert obs.category is IvaCategory.INTRA_COMMUNITY_SUPPLY
    assert _casilla_base(aggregation, "59") == Decimal("5000.00")
    assert _casilla_base(aggregation, "60") == Decimal("0")


def test_northern_ireland_xi_goods_supply_populates_casilla_59() -> None:
    """Post-Brexit XI goods stay on the intra-community supply base path."""
    tx = _inbound_tx(
        "goods-xi-01",
        amount=Decimal("3000.00"),
        taxable_base=Decimal("3000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_country="XI",
        counterparty_identification_state=_XI,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert len(aggregation.observations) == 1
    assert _casilla_base(aggregation, "59") == Decimal("3000.00")
    assert _casilla_base(aggregation, "60") == Decimal("0")


def test_domestic_not_subject_services_do_not_populate_casilla_59() -> None:
    """A DOMESTIC_NOT_SUBJECT (R12) services row does NOT feed casilla 59.

    Per cross-border contract D4: B2B services to EU taxable persons under art. 69 land in
    DOMESTIC_NOT_SUBJECT, not INTRA_COMMUNITY_SUPPLY.  The observation is
    produced (category=DOMESTIC_NOT_SUBJECT) but the casilla 59 registry binding
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
    assert _casilla_base(aggregation, "59") == Decimal("0")


def test_export_third_country_populates_casilla_60() -> None:
    """An EXPORT_THIRD_COUNTRY_ZERO_RATED row to a placed third country feeds casilla 60.

    The counterparty is positively established in the US. It used to carry no
    country at all, which passed the gate only because absence was read as
    third-country establishment -- so the fixture asserted casilla 60 from
    evidence that placed the party nowhere.
    """
    tx = _inbound_tx(
        "export-us-01",
        amount=Decimal("3000.00"),
        taxable_base=Decimal("3000.00"),
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        counterparty_country="US",
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert _casilla_base(aggregation, "60") == Decimal("3000.00")
    assert _casilla_base(aggregation, "59") == Decimal("0")


def test_export_assimilated_operation_populates_casilla_60() -> None:
    """An EXPORT_ASSIMILATED_ZERO_RATED art.22 row feeds the same casilla 60 base."""
    tx = _inbound_tx(
        "export-assimilated-ship-01",
        amount=Decimal("1750.00"),
        taxable_base=Decimal("1750.00"),
        iva_category=IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        counterparty_country="US",
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.issues) == 0, f"unexpected issues: {aggregation.issues}"
    assert _casilla_base(aggregation, "60") == Decimal("1750.00")
    assert _casilla_base(aggregation, "59") == Decimal("0")


def test_d5_intracom_with_es_identified_counterparty_is_rejected() -> None:
    """INTRA_COMMUNITY_SUPPLY to a Spanish-IDENTIFIED counterparty is a gate failure.

    The establishment is German here and deliberately so: the refusal must come
    from the Spanish IVA identification the acquirer purchases under, which is
    the fact art. 25 reads, not from where it happens to be established.
    """
    tx = _inbound_tx(
        "intracom-es-01",
        amount=Decimal("1000.00"),
        taxable_base=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_country="DE",
        counterparty_identification_state=_ES,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.observations) == 0
    assert len(aggregation.issues) == 1
    issue = aggregation.issues[0]
    assert issue.reason is IvaLedgerAggregationIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION


def test_d5_intracom_without_identification_is_rejected() -> None:
    """INTRA_COMMUNITY_SUPPLY with no identification state is a gate failure."""
    tx = _inbound_tx(
        "intracom-no-state-01",
        amount=Decimal("1000.00"),
        taxable_base=Decimal("1000.00"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_country=None,
        counterparty_identification_state=None,
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.observations) == 0
    assert len(aggregation.issues) == 1
    assert aggregation.issues[0].reason is IvaLedgerAggregationIssueReason.MISSING_COUNTERPARTY_IDENTIFICATION_STATE


def test_d5_export_with_eu_member_state_is_rejected() -> None:
    """EXPORT_THIRD_COUNTRY_ZERO_RATED with a non-None eu_member_state is rejected (contract D5)."""
    tx = _inbound_tx(
        "export-with-eu-01",
        amount=Decimal("800.00"),
        taxable_base=Decimal("800.00"),
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        counterparty_country="DE",
    )
    catalogue = TransactionCatalogue.from_transactions([tx])
    aggregation = aggregate_iva_ledger_observations(catalogue, period=_PERIOD)

    assert len(aggregation.observations) == 0
    assert len(aggregation.issues) == 1
    assert aggregation.issues[0].reason is IvaLedgerAggregationIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION


def test_d5_export_assimilated_with_eu_member_state_is_rejected() -> None:
    """EXPORT_ASSIMILATED_ZERO_RATED with a non-None eu_member_state is rejected."""
    tx = _inbound_tx(
        "export-assimilated-with-eu-01",
        amount=Decimal("800.00"),
        taxable_base=Decimal("800.00"),
        iva_category=IvaCategory.EXPORT_ASSIMILATED_ZERO_RATED,
        counterparty_country="DE",
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
        counterparty_country="DE",
        counterparty_identification_state=_DE,
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
    assert _casilla_base(aggregation, "59") == Decimal("5000.00")
    assert _casilla_base(aggregation, "60") == Decimal("0")
