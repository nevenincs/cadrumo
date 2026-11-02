"""An unsaved pattern is answered as saving and applying it would be, by the same engine."""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

import pytest

from ....core.iban import iban_mod_97
from ....domain.transactions.classification_rule import (
    RULE_PATTERN_ENTRY_MAX_LENGTH,
    LedgerClassificationRule,
    description_pattern_error,
)
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.errors import ClassificationRuleError
from ....domain.transactions.models import Transaction
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..actions_classification import classification_rule_in_scope
from ..rule_trial_operation import try_rule_pattern

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_PROFILE: Final = UUID("11111111-1111-4111-8111-111111111111")
_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerRuleTrial.json"
)


def _row(
    description: str,
    *,
    state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
    classification: BusinessClassification = BusinessClassification.NOT_YET_PROCESSED,
) -> Transaction:
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
            source_path=Path(__file__),
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


@pytest.fixture(name="rows")
def _rows() -> dict[str, Transaction]:
    return {
        "pending": _row("RECIBO ALBOR MOVIL"),
        "decided": _row("fibra albor", classification=BusinessClassification.BUSINESS),
        "archived": _row("ALBOR", state=TransactionLifecycleState.ARCHIVED),
        "other": _row("OTRA COSA"),
    }


def test_it_finds_active_movements_anywhere_ignoring_case_and_splits_what_it_would_classify(
    rows: dict[str, Transaction],
) -> None:
    answer = try_rule_pattern(_PROFILE, "albor", rows)
    assert answer.outcome == "matched"
    assert answer.hits == ("pending", "decided")
    assert answer.pending == ("pending",)
    assert all(classification_rule_in_scope(rows[item], reaffirm=False) for item in answer.pending)


def test_nothing_found_is_an_answer_not_a_refusal(rows: dict[str, Transaction]) -> None:
    answer = try_rule_pattern(_PROFILE, "zzz", rows)
    assert (answer.outcome, answer.hits, answer.pending) == ("matched", (), ())


@pytest.mark.parametrize("pattern", ["", "   ", "\t"])
def test_a_blank_pattern_is_refused_as_the_writer_refuses_it(pattern: str, rows: dict[str, Transaction]) -> None:
    answer = try_rule_pattern(_PROFILE, pattern, rows)
    assert (answer.outcome, answer.hits) == ("empty_pattern", ())


@pytest.mark.parametrize("pattern", ["[unclosed", "(", "(?P<x", "*a"])
def test_a_broken_pattern_is_refused_as_the_writer_refuses_it(pattern: str, rows: dict[str, Transaction]) -> None:
    answer = try_rule_pattern(_PROFILE, pattern, rows)
    assert (answer.outcome, answer.hits) == ("invalid_pattern", ())
    with pytest.raises((ClassificationRuleError, ValueError)):
        LedgerClassificationRule.create(
            description_pattern=pattern, classification=BusinessClassification.BUSINESS, actor="t"
        )


@pytest.mark.parametrize(
    ("pattern", "description", "found"),
    [
        # Grammar a browser would read differently or refuse: the engine's reading is the answer.
        ("(?P<who>albor)", "albor", True),
        ("(?i)ALBOR", "albor", True),
        (r"\Aalbor\Z", "albor", True),
        (r"^albor$", "x albor", False),
        (r"a\.b", "a.b", True),
        (r"a\.b", "axb", False),
    ],
)
def test_the_answer_is_the_engines_own_match(pattern: str, description: str, found: bool) -> None:
    answer = try_rule_pattern(_PROFILE, pattern, {"row": _row(description)})
    assert (answer.hits == ("row",)) is found
    assert bool(re.search(pattern, description, re.IGNORECASE)) is found


def test_every_recorded_answer_is_the_engines() -> None:
    recorded = json.loads(_RECORDING.read_text(encoding="utf-8"))
    for answer in recorded["answers"]:
        pattern = answer["description_pattern"]
        rows = {description: _row(description) for description in recorded["descriptions"]}
        live = try_rule_pattern(_PROFILE, pattern, rows)
        assert (live.outcome, list(live.hits)) == (answer["outcome"], answer["matches"]), pattern


def test_the_number_the_window_recording_refuses_is_refused_and_its_correction_is_taken() -> None:
    # 91 is the control pair of this account; worked by hand, mod 97 of the moved digits is 1.
    assert iban_mod_97("ES9121000418450200051332") == 1
    assert iban_mod_97("ES9221000418450200051332") != 1


_CATASTROPHIC: Final = r"(a+)+$"


def test_a_pattern_that_overruns_is_answered_as_one_and_the_active_rows_are_all_it_saw() -> None:
    stuck = "a" * 27 + "!"
    answer = try_rule_pattern(_PROFILE, _CATASTROPHIC, {"stuck": _row(stuck)})
    assert (answer.outcome, answer.hits, answer.pending) == ("overrun", (), ())
    archived = {"stuck": _row(stuck, state=TransactionLifecycleState.ARCHIVED)}
    assert try_rule_pattern(_PROFILE, _CATASTROPHIC, archived).outcome == "matched"


@pytest.mark.parametrize("pattern", ["a{99999999999}", "(" * 1000 + ")" * 1000, "(?L)a"])
def test_every_way_a_pattern_cannot_compile_is_the_invalid_answer(pattern: str, rows: dict[str, Transaction]) -> None:
    assert try_rule_pattern(_PROFILE, pattern, rows).outcome == "invalid_pattern"
    assert description_pattern_error(pattern) is not None
    with pytest.raises((ClassificationRuleError, ValueError)):
        LedgerClassificationRule.create(
            description_pattern=pattern, classification=BusinessClassification.BUSINESS, actor="t"
        )


def test_a_new_pattern_past_the_limit_is_too_long_yet_a_stored_rule_past_it_stays_readable(
    rows: dict[str, Transaction],
) -> None:
    longer = "albor|" + "x" * RULE_PATTERN_ENTRY_MAX_LENGTH
    assert try_rule_pattern(_PROFILE, longer, rows).outcome == "too_long"
    stored = LedgerClassificationRule.create(
        description_pattern=longer, classification=BusinessClassification.BUSINESS, actor="t"
    )
    assert LedgerClassificationRule.model_validate(stored.model_dump(mode="python")) == stored
