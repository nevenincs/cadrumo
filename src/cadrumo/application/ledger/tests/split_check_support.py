"""The parent movement and the recorded answer the split check's desktop recording holds."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..split_check_operation import LedgerSplitCheckPart, check_split

SPLIT_CHECK_PROFILE: Final = UUID("33333333-3333-4333-8333-333333333333")


def split_parent(
    amount: str = "10.00", state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE
) -> Transaction:
    moment = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
    raw = RawTransaction(
        provider_transaction_id="parent",
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=Decimal(amount),
        currency="EUR",
        counterparty="Supplier SL",
        description="Subscription",
        provenance=RawProvenance(
            source_path=Path("synthetic.csv"),
            source_sha256="0" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=moment,
            provider_name="synthetic",
        ),
        raw_fields={},
    )
    stored = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": moment,
            "modified_at": moment,
        }
    )
    return stored.model_copy(update={"lifecycle_state": state})


def recorded_split_answer(parent_amount: str, parts: Sequence[Mapping[str, str | None]]) -> dict[str, object]:
    """What the check answered for unsaved ``parts`` of an active parent movement of ``parent_amount``."""
    asked = tuple(LedgerSplitCheckPart(amount=part["amount"], description=str(part["description"])) for part in parts)
    answer = check_split(SPLIT_CHECK_PROFILE, split_parent(parent_amount), asked)
    dumped: dict[str, object] = dict(answer.model_dump(mode="json", exclude={"profile_id"}))
    return dumped
