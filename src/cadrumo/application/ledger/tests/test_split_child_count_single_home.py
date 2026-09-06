"""Both split entry points refuse a cohort of fewer than two children.

The rule lived as two byte-identical blocks, one in ``split_transaction`` and
one in the classified split. Nothing failed while they agreed, and
``_build_split_state`` — the shared builder whose docstring says the split shape
is "defined once" — did not carry it, so a third entry point would have reached
every other child-shape rule and not this one.

Fewer than two children is not a split: one child reproduces the parent under a
new id and marks the original SPLIT, leaving a lineage group whose only member
restates what it came from.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal

import pytest

from ....domain.transactions.errors import TransactionValidationError
from .. import actions_split_merge as module
from ..actions_split_merge import require_splittable_child_count
from ..models import SplitChildCommand

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "24242424-2424-4424-8424-242424242424"
_TRANSACTION = "a" * 64

#: Every public entry point that begins a split.
_SPLIT_ENTRY_POINTS = ("split_transaction", "split_transaction_with_classified_children")


def _children(count: int) -> tuple[SplitChildCommand, ...]:
    return tuple(SplitChildCommand(amount=Decimal("10.00"), description=f"child {index}") for index in range(count))


@pytest.mark.parametrize("count", [0, 1])
def test_a_cohort_smaller_than_two_is_refused(count: int) -> None:
    """Zero and one are both checked; one is the case that would persist."""
    with pytest.raises(TransactionValidationError) as excinfo:
        require_splittable_child_count(bucket_id=_BUCKET, transaction_id=_TRANSACTION, children=_children(count))

    assert getattr(excinfo.value, "context", {}).get("child_count") == count


def test_two_children_are_accepted() -> None:
    """The supported path, so the refusals above are not vacuous."""
    require_splittable_child_count(bucket_id=_BUCKET, transaction_id=_TRANSACTION, children=_children(2))


def test_the_refusal_names_the_row_it_refused() -> None:
    """An operator splitting one of many rows needs to know which one failed."""
    with pytest.raises(TransactionValidationError) as excinfo:
        require_splittable_child_count(bucket_id=_BUCKET, transaction_id=_TRANSACTION, children=())

    context = getattr(excinfo.value, "context", {})

    assert context.get("transaction_id") == _TRANSACTION
    assert context.get("bucket_id") == _BUCKET


@pytest.mark.parametrize("entry_point", _SPLIT_ENTRY_POINTS)
def test_every_split_entry_point_asks_the_shared_rule(entry_point: str) -> None:
    """Both paths must reach it, and neither may carry its own copy.

    Structural because the two copies agreed: a behavioural test of either one
    passed against the duplication, and would keep passing on the day a third
    entry point omitted the rule entirely.
    """
    source = inspect.getsource(getattr(module, entry_point))
    tree = ast.parse(source.lstrip())
    called = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}

    assert "require_splittable_child_count" in called


def test_no_split_entry_point_reimplements_the_count_check() -> None:
    """Proof the extraction actually removed the copies rather than adding a third.

    Compares against the literal comparison the duplicated blocks used, so a
    reintroduced inline check fails here even if it also calls the helper.
    """
    inline_checks = [
        entry_point
        for entry_point in _SPLIT_ENTRY_POINTS
        if any(
            isinstance(node, ast.Compare)
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "len"
            and any(isinstance(comparator, ast.Constant) and comparator.value == 2 for comparator in node.comparators)
            for node in ast.walk(ast.parse(inspect.getsource(getattr(module, entry_point)).lstrip()))
        )
    ]

    assert inline_checks == []
