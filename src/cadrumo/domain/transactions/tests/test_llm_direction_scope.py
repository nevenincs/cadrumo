"""The classifier prompt says which way the money moved, and offers expense categories only for outgoing rows.

A bank amount is a magnitude, so without the direction an incoming transfer
reads exactly like a payment, and a small model files income under an expense
category. Every case runs the real prompt render and the real parser.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.tests.authored_editions import filing_year_envelope
from ..enums import BusinessClassification, TransactionDirection
from ..errors import LLMClassifierError
from ..llm import (
    PromptSpec,
    build_split_prompt,
    parse_response,
    parse_split_response,
    prompt_spec_with_every_spending_category,
)
from ..models import Transaction
from ..raw_transaction import RawProvenance, RawTransaction, SourceFormat

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATEGORY_HEADING = "SpendingCategory"


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned, validating_governed_facts(pinned):
        yield pinned


@pytest.fixture(scope="module")
def spec(operation: PinnedAuthorityOperation) -> PromptSpec:
    return prompt_spec_with_every_spending_category(year=filing_year_envelope().horizon, operation=operation)


def _transaction(direction: TransactionDirection, description: str) -> Transaction:
    booked = date(filing_year_envelope().horizon, 3, 1)
    raw = RawTransaction(
        provider_transaction_id=f"row-{direction.value.lower()}",
        booked_date=booked,
        value_date=booked,
        amount=Decimal("29.00"),
        currency="EUR",
        counterparty="Nube Ejemplo SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime.combine(booked, datetime.min.time(), tzinfo=UTC),
            provider_name="manual",
        ),
        raw_fields={"Concepto": description},
    )
    return Transaction.model_validate(
        {"raw": raw, "direction": direction, "group_label": None, "source_jurisdiction": "ES"},
    )


def _reply(category: str | None) -> str:
    body: dict[str, str] = {"classification": "BUSINESS", "confidence": "0.9", "reason": "Named on the row."}
    if category is not None:
        body["category"] = category
    return json.dumps(body)


def test_an_outgoing_row_is_offered_the_expense_categories(
    spec: PromptSpec, operation: PinnedAuthorityOperation
) -> None:
    with validating_governed_facts(operation):
        row = _transaction(TransactionDirection.OUTGOING, "PAGO CLOUD SERVICIOS")
    scoped = spec.for_direction(row.direction)
    prompt = scoped.render(row)
    category = spec.categories[0].value

    assert "Direction: OUTGOING" in prompt
    assert _CATEGORY_HEADING in prompt
    assert scoped.allowed_categories() == spec.allowed_categories()
    assert parse_response(_reply(category.value), spec=scoped).category == category


@pytest.mark.parametrize("direction", [TransactionDirection.INCOMING, TransactionDirection.INTERNAL_TRANSFER])
def test_a_row_that_is_not_a_payment_is_offered_no_expense_category(
    spec: PromptSpec, operation: PinnedAuthorityOperation, direction: TransactionDirection
) -> None:
    with validating_governed_facts(operation):
        row = _transaction(direction, "TRANSF RECIBIDA CLIENTE")
    scoped = spec.for_direction(row.direction)
    prompt = scoped.render(row)

    assert f"Direction: {direction.value}" in prompt
    assert _CATEGORY_HEADING not in prompt
    assert scoped.allowed_categories() == frozenset()
    assert parse_response(_reply(None), spec=scoped).classification is BusinessClassification.BUSINESS
    with pytest.raises(LLMClassifierError, match="unexpected category"):
        parse_response(_reply(spec.categories[0].value.value), spec=scoped)


def test_a_split_of_an_incoming_row_refuses_an_expense_category(
    spec: PromptSpec, operation: PinnedAuthorityOperation
) -> None:
    with validating_governed_facts(operation):
        row = _transaction(TransactionDirection.INCOMING, "TRANSF RECIBIDA CLIENTE")
    scoped = spec.for_direction(row.direction)
    category = spec.categories[0].value.value

    def reply(first_category: str | None) -> str:
        first: dict[str, str] = {"proportion": "0.5"}
        if first_category is not None:
            first["category"] = first_category
        return json.dumps({"reason": "Two lines.", "children": [first, {"proportion": "0.5"}]})

    assert "Direction: INCOMING" in build_split_prompt(row, spec=scoped, evidence_text="Factura")
    assert parse_split_response(reply(None), spec=scoped).recommends_split
    with pytest.raises(LLMClassifierError, match="category"):
        parse_split_response(reply(category), spec=scoped)
