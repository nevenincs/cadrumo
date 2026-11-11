"""A rate refusal on a movement-dated ledger row names the date it judged.

A ledger row with no ``operation_date`` takes its bank movement date -- the
value date, else the booked date -- as its LIVA art. 75 devengo date, and
art. 90.Dos prices it at the rate in force then. When that rate is no longer
in force on the movement date, the refusal used to read as a wrong rate, while
the fact actually missing may be the operation date. These tests drive real
rows through the real resolver and the source resolver's marker; which date
is used is unchanged.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.i18n.render import tr as render_tr
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.invoices.tests.invoice_catalogue_seed import window_middle
from ....domain.iva.lookup import coexisting_tier_rates
from ....domain.iva.schema import IvaRateKind, spanish_eu_member_state
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..iva_ledger import (
    IvaLedgerAggregation,
    IvaLedgerAggregationIssueReason,
    IvaLedgerRowDateSource,
    aggregate_iva_ledger_observations,
)
from ..modelo_bindings_iva import selected_scope_iva_evidence_message

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RATE = Decimal("0.02")
_BASE = Decimal("1000.00")
_CUOTA = Decimal("20.00")
# A date inside the registry's temporary 2 % super-reducido window; only the
# window's end date is load-bearing, and that is read from the registry.
_WINDOW_PROBE = window_middle("RATE_2")


def _rate_until() -> date:
    with bundled_indexed_authority().operation() as operation:
        (window,) = (
            record
            for record in coexisting_tier_rates(
                spanish_eu_member_state(effective_date=_WINDOW_PROBE, authority=operation),
                IvaRateKind("super_reduced"),
                _WINDOW_PROBE,
                operation=operation,
            )
            if record.pct == _RATE * 100
        )
    assert window.effective_until is not None
    return window.effective_until


def _quarter_of(day: date) -> Period:
    return Period.from_year_and_code(day.year, f"{(day.month - 1) // 3 + 1}T")


def _sale(
    provider_id: str,
    *,
    value_date: date | None,
    booked_date: date,
    operation_date: date | None = None,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": RawTransaction(
                provider_transaction_id=provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=_BASE + _CUOTA,
                currency="EUR",
                counterparty="Cliente",
                description=f"ledger row {provider_id}",
                provenance=RawProvenance(
                    source_path=Path(__file__),
                    source_sha256="c" * 64,
                    source_row_index=1,
                    source_format=SourceFormat.MANUAL,
                    ingested_at=datetime.combine(booked_date, datetime.min.time(), tzinfo=UTC),
                    provider_name="manual-ledger",
                ),
                raw_fields={"source_kind": "ledger_transaction"},
            ),
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _BASE,
            "iva_rate": _RATE,
            "iva_amount": _CUOTA,
            "operation_date": operation_date,
            "classified_at": datetime.combine(booked_date, datetime.min.time(), tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregate(transaction: Transaction, period: Period) -> IvaLedgerAggregation:
    with bundled_indexed_authority().operation() as operation:
        return aggregate_iva_ledger_observations(
            TransactionCatalogue.from_transactions((transaction,)),
            period=period,
            ledger_profile_id="test-profile",
            operation=operation,
        )


def test_a_value_dated_row_past_the_rate_names_the_movement_date() -> None:
    moved = _rate_until() + timedelta(days=15)

    result = _aggregate(_sale("moved-after", value_date=moved, booked_date=moved), _quarter_of(moved))

    assert result.observations == ()
    (issue,) = result.issues
    assert issue.reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE
    assert issue.operation_date_source is IvaLedgerRowDateSource.VALUE_DATE
    assert issue.detail == render_tr(
        "aggregation.iva_ledger.errors.unsupported_iva_rate_on_movement_date",
        rate=str(_RATE),
        date=moved.isoformat(),
    )
    # The source resolver's durable marker carries the sentence, not the bare reason.
    assert selected_scope_iva_evidence_message(issue).endswith(issue.detail)


def test_a_row_with_only_a_booked_date_names_that_source() -> None:
    booked = _rate_until() + timedelta(days=15)

    result = _aggregate(_sale("booked-only", value_date=None, booked_date=booked), _quarter_of(booked))

    (issue,) = result.issues
    assert issue.reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE
    assert issue.operation_date_source is IvaLedgerRowDateSource.BOOKED_DATE


def test_a_recorded_operation_date_before_the_end_is_accepted() -> None:
    """The remedy the refusal names: the same movement with its delivery date recorded."""
    rate_until = _rate_until()
    delivered = rate_until - timedelta(days=15)
    moved = rate_until + timedelta(days=15)

    result = _aggregate(
        _sale("delivered-before", value_date=moved, booked_date=moved, operation_date=delivered),
        _quarter_of(delivered),
    )

    assert result.issues == ()
    (observation,) = result.observations
    assert observation.transaction_date == delivered
    assert observation.applied_rate == _RATE


def test_a_recorded_operation_date_past_the_rate_keeps_the_rate_wording() -> None:
    """When the operation date itself is past the rate, the rate is what to look at."""
    delivered = _rate_until() + timedelta(days=15)

    result = _aggregate(
        _sale("delivered-after", value_date=delivered, booked_date=delivered, operation_date=delivered),
        _quarter_of(delivered),
    )

    (issue,) = result.issues
    assert issue.reason is IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE
    assert issue.operation_date_source is IvaLedgerRowDateSource.OPERATION_DATE
    assert delivered.isoformat() in issue.detail
    assert issue.detail != render_tr(
        "aggregation.iva_ledger.errors.unsupported_iva_rate_on_movement_date",
        rate=str(_RATE),
        date=delivered.isoformat(),
    )
    assert selected_scope_iva_evidence_message(issue) == "selected-scope IVA evidence failure: unsupported_iva_rate"
