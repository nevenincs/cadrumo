"""Build ledger rows that carry a rental link, for the tests that exercise it."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..enums import TransactionDirection
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat


def booked_date(year: int | None = None) -> date:
    """Return a booking date in ``year``, by default the newest year the registry supports."""
    return date(year if year is not None else filing_year_envelope().horizon, 3, 14)


def rental_row(*, provider_id: str = "rental-link-row", **fields: object) -> Transaction:
    """Return one validated ledger row with ``fields`` layered over a plain outgoing row."""
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date(),
        value_date=None,
        amount=Decimal("85.00"),
        currency="EUR",
        counterparty="Comunidad de propietarios",
        description="cuota trimestral",
        provenance=RawProvenance(
            source_path=Path("rental-link.csv"),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime.combine(booked_date() + timedelta(days=1), time(8, 0), tzinfo=UTC),
            provider_name="rental link provider",
        ),
        raw_fields={},
    )
    payload: dict[str, object] = {
        "raw": raw,
        "direction": TransactionDirection.OUTGOING,
        "group_label": None,
        "source_jurisdiction": "ES",
    }
    payload.update(fields)
    return Transaction.model_validate(payload)
