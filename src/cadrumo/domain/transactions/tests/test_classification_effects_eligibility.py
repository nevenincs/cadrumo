"""What a row's stored codes decide, each worked by hand from what the writers enforce."""

from __future__ import annotations

import pytest

from ..classification_effects import (
    advises_purchase_evidence,
    awaits_invoice,
    lifecycle_actions_taken,
    takes_changes,
    takes_classification,
    takes_invoice,
    takes_m210_income,
)
from ..enums import BusinessClassification as Class
from ..enums import TransactionDirection as Direction
from ..enums import TransactionLifecycleState as Lifecycle

pytestmark = [pytest.mark.unit]


def test_only_an_active_row_takes_a_change() -> None:
    assert [state for state in Lifecycle if takes_changes(state)] == [Lifecycle.ACTIVE]


def test_a_transfer_is_never_classified_as_tax_relevant_business() -> None:
    refused = {
        classification
        for classification in Class
        if not takes_classification(Direction.INTERNAL_TRANSFER, classification)
    }
    assert Class.BUSINESS in refused
    assert Class.MIXED in refused
    assert Class.PERSONAL not in refused
    for direction in (Direction.INCOMING, Direction.OUTGOING):
        assert all(takes_classification(direction, classification) for classification in Class)


def test_a_transfer_is_offered_no_invoice_and_only_income_carries_modelo_210() -> None:
    assert not takes_invoice(Direction.INTERNAL_TRANSFER)
    assert takes_invoice(Direction.INCOMING)
    assert takes_invoice(Direction.OUTGOING)
    assert [direction for direction in Direction if takes_m210_income(direction)] == [Direction.INCOMING]


@pytest.mark.parametrize(
    ("lifecycle", "direction", "classification", "linked", "expected"),
    [
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.BUSINESS, False, True),
        (Lifecycle.ACTIVE, Direction.INCOMING, Class.MIXED, False, True),
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.BUSINESS, True, False),
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.PERSONAL, False, False),
        (Lifecycle.ACTIVE, Direction.INTERNAL_TRANSFER, Class.BUSINESS, False, False),
        (Lifecycle.ARCHIVED, Direction.OUTGOING, Class.BUSINESS, False, False),
    ],
)
def test_who_waits_for_an_invoice(
    lifecycle: Lifecycle, direction: Direction, classification: Class, linked: bool, expected: bool
) -> None:
    assert awaits_invoice(lifecycle, direction, classification, linked=linked) is expected


@pytest.mark.parametrize(
    ("lifecycle", "direction", "classification", "has_evidence", "expected"),
    [
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.BUSINESS, False, True),
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.MIXED, False, True),
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.MIXED, True, False),
        (Lifecycle.ACTIVE, Direction.INCOMING, Class.BUSINESS, False, False),
        (Lifecycle.ACTIVE, Direction.OUTGOING, Class.PERSONAL, False, False),
        (Lifecycle.STASHED, Direction.OUTGOING, Class.BUSINESS, False, False),
    ],
)
def test_who_is_told_a_purchase_document_is_missing(
    lifecycle: Lifecycle, direction: Direction, classification: Class, has_evidence: bool, expected: bool
) -> None:
    assert advises_purchase_evidence(lifecycle, direction, classification, has_evidence=has_evidence) is expected


@pytest.mark.parametrize(
    ("lifecycle", "classification", "expected"),
    [
        (Lifecycle.ACTIVE, Class.PERSONAL, ("archive", "stash", "exclude")),
        (Lifecycle.ACTIVE, Class.REVIEWED_EXCLUDED, ("archive", "stash")),
        (Lifecycle.ARCHIVED, Class.PERSONAL, ("restore",)),
        (Lifecycle.STASHED, Class.BUSINESS, ("restore",)),
        (Lifecycle.SPLIT, Class.PERSONAL, ()),
    ],
)
def test_what_lifecycle_actions_are_offered(
    lifecycle: Lifecycle, classification: Class, expected: tuple[str, ...]
) -> None:
    assert lifecycle_actions_taken(lifecycle, classification) == expected
