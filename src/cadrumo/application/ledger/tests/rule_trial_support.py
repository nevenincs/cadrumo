"""Movements and the recorded answer the rule trial's desktop recording holds."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..rule_trial_operation import try_rule_pattern

RULE_TRIAL_PROFILE: Final = UUID("11111111-1111-4111-8111-111111111111")


def rule_trial_row(
    description: str,
    *,
    state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> Transaction:
    """A synthetic outgoing movement of ``description``, keyed by nothing but the text it carries."""
    moment = datetime(2024, 4, 14, 9, 30, tzinfo=UTC)
    raw = RawTransaction(
        provider_transaction_id=description,
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=Decimal("10.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path("synthetic.csv"),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=moment,
            provider_name="test",
        ),
        raw_fields={},
    )
    stored = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": classification,
            "source_jurisdiction": "ES",
            "group_label": None,
            "created_at": moment,
            "modified_at": moment,
        }
    )
    return stored.model_copy(update={"lifecycle_state": state})


def recorded_rule_trial_answer(descriptions: Sequence[str], pattern: str) -> dict[str, object]:
    """What the trial answered for ``pattern`` over a ledger holding one active movement per description."""
    rows = {description: rule_trial_row(description) for description in descriptions}
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, pattern, rows)
    return {"description_pattern": pattern, "outcome": answer.outcome, "matches": list(answer.hits)}
