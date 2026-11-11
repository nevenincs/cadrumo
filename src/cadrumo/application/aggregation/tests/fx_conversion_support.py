"""USD raw transaction shared by the FX conversion suites."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

USD_AMOUNT = Decimal("100.00")

_BOOKING_DAY = date(filing_year_envelope().horizon, 1, 15)


def usd_raw(provider_id: str, *, amount: Decimal = USD_AMOUNT) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=_BOOKING_DAY,
        value_date=_BOOKING_DAY,
        amount=amount,
        currency="USD",
        counterparty="Acme Corp",
        description=f"USD invoice {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(1980, 1, 16, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Reference": provider_id},
    )
