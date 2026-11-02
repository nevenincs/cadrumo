"""The split check answers unsaved parts as the real split writer takes them."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.errors import TransactionValidationError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .. import actions_split_merge as writer
from ..models import SplitChildCommand
from ..split_check_operation import LedgerSplitCheckPart, LedgerSplitCheckResult, check_split
from ..split_operation import LEDGER_SPLIT_CHILDREN_MAX, LEDGER_SPLIT_PART_DESCRIPTION_MAX, LedgerSplitChildRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE: Final = UUID("33333333-3333-4333-8333-333333333333")
_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerSplitCheck.json"
)


def _parent(amount: str = "10.00", state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE) -> Transaction:
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
            source_path=Path(__file__),
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


def _writer_shape_takes(parent: Transaction, children: tuple[SplitChildCommand, ...]) -> bool:
    """Run the writer's own shape checks and child building, everything but its storage."""
    try:
        writer.require_splittable_child_count(bucket_id=str(_PROFILE), transaction_id="p", children=children)
        writer._validate_split_child_amounts(parent_amount=parent.raw.amount, children=children)
        built = writer._build_initial_split_children(
            parent=parent,
            children=children,
            occurred_at=datetime(2024, 5, 1, tzinfo=UTC),
            actor="operator",
            source_command="synthetic",
        )
        writer._require_unique_split_child_ids(built)
    except TransactionValidationError:
        return False
    return True


def _ask(parent: Transaction, *parts: tuple[str | None, str]) -> LedgerSplitCheckResult:
    return check_split(
        _PROFILE,
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
    parent = _parent()
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
    answer = _ask(_parent("59.99"), ("20.00", " Licencia "), (None, "Soporte"))

    assert answer.problem is None
    assert answer.remainder == "39.99"
    assert [(child.amount, child.description) for child in answer.children] == [
        ("20", "Licencia"),
        ("39.99", "Soporte"),
    ]
    commands = tuple(SplitChildCommand(amount=Decimal(c.amount), description=c.description) for c in answer.children)
    assert _writer_shape_takes(_parent("59.99"), commands)


def test_two_parts_alike_are_taken_because_the_writer_tells_them_apart_by_their_place() -> None:
    parent = _parent()
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
    answer = _ask(_parent(), (typed, "a"), (None, "b"))

    assert answer.remainder == remainder
    assert (answer.problem.kind if answer.problem else None) == kind
    assert (answer.problem.over if answer.problem else None) == over
    assert (answer.problem.difference if answer.problem else None) == difference


def test_the_remainder_keeps_a_parent_amount_finer_than_a_cent() -> None:
    answer = _ask(_parent("10.1255"), ("4", "a"), (None, "b"))

    assert answer.problem is None
    assert answer.remainder == "6.1255"
    assert [child.amount for child in answer.children] == ["4", "6.1255"]


def test_a_remainder_the_request_could_not_spell_is_refused_at_its_part() -> None:
    answer = _ask(_parent("10.125"), ("4", "a"), (None, "b"))

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
    answer = _ask(_parent(str(amount)), *((str(Decimal(1)), f"part {at}") for at in range(count)))

    assert (answer.problem is None) is taken
    if not taken:
        assert answer.problem is not None
        assert answer.problem.kind == "count"
        assert answer.problem.max == LEDGER_SPLIT_CHILDREN_MAX


def test_the_description_boundary_is_the_writers() -> None:
    at_the_limit = "x" * LEDGER_SPLIT_PART_DESCRIPTION_MAX
    assert _ask(_parent(), ("6", at_the_limit), ("4", "b")).problem is None
    over = _ask(_parent(), ("6", "a"), ("4", at_the_limit + "x")).problem
    assert over is not None
    assert (over.kind, over.index, over.max) == ("description_long", 1, LEDGER_SPLIT_PART_DESCRIPTION_MAX)
    with pytest.raises(ValidationError):
        LedgerSplitChildRequest(amount="4", description=at_the_limit + "x")
    with pytest.raises(ValidationError):
        LedgerSplitChildRequest(amount="4", description="   ")


def test_a_movement_gone_or_not_active_is_not_split() -> None:
    gone = check_split(_PROFILE, None, ()).problem
    assert gone is not None
    assert gone.kind == "gone"

    archived = _parent(state=TransactionLifecycleState.ARCHIVED)
    answer = _ask(archived, ("6", "a"), ("4", "b")).problem
    assert answer is not None
    assert answer.kind == "not_active"
    with pytest.raises(TransactionValidationError, match="only active"):
        writer._resolve_active_split_parent(
            TransactionCatalogue.model_validate({"transactions": {archived.transaction_id: archived}}),
            bucket_id=str(_PROFILE),
            transaction_id=archived.transaction_id,
        )


def test_every_recorded_answer_is_the_live_one() -> None:
    recording = json.loads(_RECORDING.read_text(encoding="utf-8"))
    assert recording["answers"]
    for entry in recording["answers"]:
        parts = tuple(
            LedgerSplitCheckPart(amount=part["amount"], description=part["description"]) for part in entry["parts"]
        )
        live = check_split(_PROFILE, _parent(entry["parent_amount"]), parts)
        assert live.model_dump(mode="json", exclude={"profile_id"}) == entry["answer"], entry["parts"]
