"""The split check answers unsaved parts as the real split writer takes them."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import pytest
from pydantic import ValidationError

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.enums import TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from .. import actions_split_merge as writer
from ..models import SplitChildCommand
from ..split_check_operation import LedgerSplitCheckPart, LedgerSplitCheckResult, check_split
from ..split_operation import LEDGER_SPLIT_CHILDREN_MAX, LEDGER_SPLIT_PART_DESCRIPTION_MAX, LedgerSplitChildRequest
from .split_check_support import SPLIT_CHECK_PROFILE, recorded_split_answer, split_parent

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_QUESTIONS: Final = (
    Path(__file__).resolve().parents[5] / "dev/fixtures/ledger-recording-questions/ledgerSplitCheck.json"
)

#: What each committed question must answer, in the file's order, worked from the split rules: the one part left
#: without an amount takes what the others leave and must come out positive, an amount has at most two decimals
#: and is positive, the parts must add up to the parent, a part needs a description, and there are two or more.
#: Each is the parent amount, the remainder, the problem's kind and part index, and the children's amounts.
_EXPECTED: Final[tuple[tuple[str, str | None, str | None, int | None, tuple[str, ...]], ...]] = (
    ("59.99", None, "amount", 0, ()),
    ("59.99", "39.99", None, None, ("20", "39.99")),
    ("59.99", "39.99", None, None, ("20", "39.99")),
    ("100", "50", None, None, ("40.5", "9.5", "50")),
    ("10.20", "0.1", None, None, ("10.1", "0.1")),
    ("10", None, "amount", 1, ()),
    ("10", None, "sum", None, ()),
    ("10", None, "amount", 0, ()),
    ("10", None, "sum", None, ()),
    ("10", None, "sum", None, ()),
    ("10", None, "amount", 0, ()),
    ("10", "5", "description", 1, ()),
    ("10", None, "count", None, ()),
)


def _writer_shape_takes(parent: Transaction, children: tuple[SplitChildCommand, ...]) -> bool:
    """Run the writer's own shape checks and child building, everything but its storage."""
    try:
        writer.require_splittable_child_count(bucket_id=str(SPLIT_CHECK_PROFILE), transaction_id="p", children=children)
        writer.validate_split_child_amounts(parent_amount=parent.raw.amount, children=children)
        built = writer.build_initial_split_children(
            parent=parent,
            children=children,
            occurred_at=datetime(_YEAR, 5, 1, tzinfo=UTC),
            actor="operator",
            source_command="synthetic",
        )
        writer.require_unique_split_child_ids(built)
    except TransactionValidationError:
        return False
    return True


def _ask(parent: Transaction, *parts: tuple[str | None, str]) -> LedgerSplitCheckResult:
    return check_split(
        SPLIT_CHECK_PROFILE,
        parent,
        tuple(LedgerSplitCheckPart(amount=amount, description=description) for amount, description in parts),
    )


@pytest.mark.parametrize(
    ("parts", "kind", "index"),
    (
        ((("6", "a"), ("4", "b")), None, None),
        ((("6.00", "a"), ("4.0", "b")), None, None),
        ((("10", "a"),), "count", None),
        ((("6", "a"), ("5", "b")), "sum", None),
        ((("5", "a"), ("4.5", "b")), "sum", None),
        ((("0", "a"), ("10", "b")), "amount", 0),
        ((("10", "a"), ("0", "b")), "amount", 1),
        ((("-1", "a"), ("11", "b")), "amount", 0),
        ((("6", ""), ("4", "b")), "description", 0),
        ((("6", "a"), ("4", "   ")), "description", 1),
    ),
    ids=(
        "takes",
        "takes-any-spelling",
        "one-part",
        "over",
        "short",
        "zero-first",
        "zero-last",
        "negative",
        "blank",
        "spaces",
    ),
)
def test_the_answer_refuses_what_the_writer_refuses_and_takes_what_it_takes(
    parts: tuple[tuple[str, str], ...], kind: str | None, index: int | None
) -> None:
    parent = split_parent()
    answer = _ask(parent, *parts)

    assert (answer.problem.kind if answer.problem else None) == kind
    assert (answer.problem.index if answer.problem else None) == index
    commands = tuple(
        SplitChildCommand(amount=Decimal(amount.strip()), description=description.strip() or "x")
        for amount, description in parts
    )
    # The writer's request model owns a blank description, as test_the_description_boundary shows.
    if kind != "description":
        assert _writer_shape_takes(parent, commands) is (kind is None)


def test_an_answer_the_writer_takes_is_handed_over_as_its_request_spells_it() -> None:
    answer = _ask(split_parent("59.99"), ("20.00", " Licencia "), (None, "Soporte"))

    assert answer.problem is None
    assert answer.remainder == "39.99"
    assert [(child.amount, child.description) for child in answer.children] == [
        ("20", "Licencia"),
        ("39.99", "Soporte"),
    ]
    commands = tuple(SplitChildCommand(amount=Decimal(c.amount), description=c.description) for c in answer.children)
    assert _writer_shape_takes(split_parent("59.99"), commands)


def test_two_parts_alike_are_taken_because_the_writer_tells_them_apart_by_their_place() -> None:
    parent = split_parent()
    answer = _ask(parent, ("5", "same"), ("5", "same"))

    assert answer.problem is None
    assert _writer_shape_takes(parent, tuple(SplitChildCommand(amount=Decimal(5), description="same") for _ in "ab"))


@pytest.mark.parametrize(
    ("typed", "remainder", "kind", "over", "difference"),
    (
        ("4", "6", None, None, None),
        ("10", None, "amount", None, None),
        ("11", None, "sum", True, "1"),
        ("", None, "amount", None, None),
        ("1.000", None, "amount", None, None),
    ),
    ids=("leaves", "leaves-nothing", "leaves-less-than-nothing", "blank", "spanish-thousand"),
)
def test_the_last_part_takes_what_the_others_leave(
    typed: str, remainder: str | None, kind: str | None, over: bool | None, difference: str | None
) -> None:
    answer = _ask(split_parent(), (typed, "a"), (None, "b"))

    assert answer.remainder == remainder
    assert (answer.problem.kind if answer.problem else None) == kind
    assert (answer.problem.over if answer.problem else None) == over
    assert (answer.problem.difference if answer.problem else None) == difference


def test_the_remainder_keeps_a_parent_amount_finer_than_a_cent() -> None:
    answer = _ask(split_parent("10.1255"), ("4", "a"), (None, "b"))

    assert answer.problem is None
    assert answer.remainder == "6.1255"
    assert [child.amount for child in answer.children] == ["4", "6.1255"]


def test_a_remainder_the_request_could_not_spell_is_refused_at_its_part() -> None:
    answer = _ask(split_parent("10.125"), ("4", "a"), (None, "b"))

    assert answer.problem is not None
    assert (answer.problem.kind, answer.problem.index) == ("amount", 1)
    with pytest.raises(ValidationError):
        LedgerSplitChildRequest(amount="6.125", description="b")


@pytest.mark.parametrize(
    ("count", "taken"),
    ((1, False), (2, True), (LEDGER_SPLIT_CHILDREN_MAX, True), (LEDGER_SPLIT_CHILDREN_MAX + 1, False)),
)
def test_the_part_count_boundaries(count: int, taken: bool) -> None:
    amount = Decimal(count)
    answer = _ask(split_parent(str(amount)), *((str(Decimal(1)), f"part {at}") for at in range(count)))

    assert (answer.problem is None) is taken
    if not taken:
        assert answer.problem is not None
        assert answer.problem.kind == "count"
        assert answer.problem.max == LEDGER_SPLIT_CHILDREN_MAX


def test_the_description_boundary_is_the_writers() -> None:
    at_the_limit = "x" * LEDGER_SPLIT_PART_DESCRIPTION_MAX
    assert _ask(split_parent(), ("6", at_the_limit), ("4", "b")).problem is None
    over = _ask(split_parent(), ("6", "a"), ("4", at_the_limit + "x")).problem
    assert over is not None
    assert (over.kind, over.index, over.max) == ("description_long", 1, LEDGER_SPLIT_PART_DESCRIPTION_MAX)
    with pytest.raises(ValidationError):
        LedgerSplitChildRequest(amount="4", description=at_the_limit + "x")
    with pytest.raises(ValidationError):
        LedgerSplitChildRequest(amount="4", description="   ")


def test_a_movement_gone_or_not_active_is_not_split() -> None:
    gone = check_split(SPLIT_CHECK_PROFILE, None, ()).problem
    assert gone is not None
    assert gone.kind == "gone"

    archived = split_parent(state=TransactionLifecycleState.ARCHIVED)
    answer = _ask(archived, ("6", "a"), ("4", "b")).problem
    assert answer is not None
    assert answer.kind == "not_active"
    with pytest.raises(TransactionValidationError, match="only active"):
        writer.resolve_active_split_parent(
            TransactionCatalogue.model_validate({"transactions": {archived.transaction_id: archived}}),
            bucket_id=str(SPLIT_CHECK_PROFILE),
            transaction_id=archived.transaction_id,
        )


def test_the_committed_questions_are_the_ones_the_expectations_state() -> None:
    asked = json.loads(_QUESTIONS.read_text(encoding="utf-8"))["answers"]

    assert [entry["parent_amount"] for entry in asked] == [expected[0] for expected in _EXPECTED]


def test_every_committed_question_is_answered_as_the_split_rules_say() -> None:
    asked = json.loads(_QUESTIONS.read_text(encoding="utf-8"))["answers"]
    assert len(asked) == len(_EXPECTED)
    for entry, (_, remainder, kind, index, amounts) in zip(asked, _EXPECTED, strict=True):
        answer = recorded_split_answer(entry["parent_amount"], entry["parts"])
        problem = cast(dict[str, object] | None, answer["problem"])
        children = cast(list[dict[str, str]], answer["children"])
        assert answer["remainder"] == remainder, entry["parts"]
        assert (None if problem is None else (problem["kind"], problem["index"])) == (
            None if kind is None else (kind, index)
        ), entry["parts"]
        assert tuple(child["amount"] for child in children) == amounts, entry["parts"]
