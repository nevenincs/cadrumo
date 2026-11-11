"""A new or edited foreign-currency row must carry a euro value that follows its rate.

Expected figures are derived by hand: 1000.00 USD at 0.92 is exactly 920.00 EUR;
333.33 at 0.9 is 299.997 which rounds half-up to 300.00.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ....domain.currency.models import EurRateLookup, EurRateLookupStatus
from ....domain.currency.service import CurrencyNormalizationService
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction
from ..actions_manual import carry_forward_fx, transaction_from_command
from ..fx_value_consistency import require_consistent_fx_value
from ..models import ManualLedgerTransactionCommand
from .transaction_row_support import outgoing_manual_row

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_NOW = datetime(_YEAR, 3, 2, tzinfo=UTC)


class _FixedRates:
    rate_source_id = "synthetic-reference"

    def lookup_eur_rate(self, currency: str, rate_date: date) -> EurRateLookup:
        return EurRateLookup(
            status=EurRateLookupStatus.FOUND,
            rate_date=rate_date,
            source=self.rate_source_id,
            rate=Decimal("0.92"),
            observation_date=date(_YEAR, 2, 27),
        )


def _usd(*, amount: str, rate: str, value_in_eur: str, **extra: object) -> Transaction:
    row = outgoing_manual_row("p", amount=Decimal(amount), currency="USD", counterparty="V", description="d")
    return row.model_copy(update={"fx_rate": Decimal(rate), "value_in_eur": Decimal(value_in_eur), **extra})


def test_a_consistent_usd_row_is_accepted() -> None:
    require_consistent_fx_value(_usd(amount="1000.00", rate="0.92", value_in_eur="920.00"))


def test_half_up_rounding_is_the_reference() -> None:
    require_consistent_fx_value(_usd(amount="333.33", rate="0.9", value_in_eur="300.00"))


def test_an_inconsistent_value_is_refused_with_a_structured_code() -> None:
    with pytest.raises(TransactionValidationError) as caught:
        require_consistent_fx_value(_usd(amount="1000.00", rate="0.92", value_in_eur="900.00"))

    assert caught.value.translated_message == "application.ledger.errors.fx_value_inconsistent"
    context = caught.value.context
    assert context is not None
    assert context["expected_value_in_eur"] == "920.00"
    assert context["value_in_eur"] == "900.00"


def test_one_cent_off_is_admitted_and_two_cents_off_is_refused() -> None:
    require_consistent_fx_value(_usd(amount="1000.00", rate="0.92", value_in_eur="920.01"))
    require_consistent_fx_value(_usd(amount="1000.00", rate="0.92", value_in_eur="919.99"))
    with pytest.raises(TransactionValidationError):
        require_consistent_fx_value(_usd(amount="1000.00", rate="0.92", value_in_eur="920.02"))
    with pytest.raises(TransactionValidationError):
        require_consistent_fx_value(_usd(amount="1000.00", rate="0.92", value_in_eur="919.98"))


def test_a_euro_row_is_unaffected() -> None:
    euro = outgoing_manual_row("p", amount=Decimal("50.00"), currency="EUR", counterparty="V", description="d")

    require_consistent_fx_value(euro)


def test_a_stored_inconsistent_record_still_loads_and_keeps_its_stored_value() -> None:
    from ...aggregation.currency_predicates import effective_eur_amount

    stored = _usd(amount="1000.00", rate="0.92", value_in_eur="900.00")
    reloaded = Transaction.model_validate_json(stored.model_dump_json())

    assert effective_eur_amount(reloaded) == Decimal("900.00")


def _command(amount: str, currency: str = "USD") -> ManualLedgerTransactionCommand:
    return ManualLedgerTransactionCommand(
        bucket_id="p",
        booked_date=date(_YEAR, 3, 1),
        amount=Decimal(amount),
        currency=currency,
        direction=TransactionDirection.OUTGOING,
        description="software",
        actor="operator",
        source_command="aeat app ledger add",
    )


def test_manual_entry_records_the_rate_provenance() -> None:
    built = transaction_from_command(
        _command("1000.00"),
        occurred_at=_NOW,
        currency_normalizer=CurrencyNormalizationService(rate_provider=_FixedRates()),
    )

    assert built.value_in_eur == Decimal("920.00")
    assert built.rate_source == "synthetic-reference"
    assert built.rate_date == date(_YEAR, 3, 1).isoformat()


def test_an_unchanged_fx_edit_keeps_the_stored_provenance() -> None:
    stored = _usd(
        amount="1000.00",
        rate="0.92",
        value_in_eur="920.00",
        rate_source="synthetic-reference",
        rate_date=date(_YEAR, 3, 1).isoformat(),
    )
    rebuilt = outgoing_manual_row("p", amount=Decimal("1000.00"), currency="USD", counterparty="V", description="e")

    carried = carry_forward_fx(stored, rebuilt)

    assert carried.rate_source == "synthetic-reference"
    assert carried.rate_date == date(_YEAR, 3, 1).isoformat()
