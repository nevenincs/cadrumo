"""An unsaved pattern is answered as saving and applying it would be, by the same engine."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Final

import pytest

from ....core.iban import iban_mod_97
from ....domain.transactions.classification_rule import (
    RULE_PATTERN_ENTRY_MAX_LENGTH,
    LedgerClassificationRule,
    description_pattern_error,
)
from ....domain.transactions.enums import BusinessClassification, TransactionLifecycleState
from ....domain.transactions.errors import ClassificationRuleError
from ....domain.transactions.models import Transaction
from ..actions_classification import classification_rule_in_scope
from ..rule_trial_operation import try_rule_pattern
from .rule_trial_support import RULE_TRIAL_PROFILE, recorded_rule_trial_answer, rule_trial_row

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RECORDING: Final = (
    Path(__file__).resolve().parents[5] / "native/desktop/frontend/src/dev/fixtures/ledgerRuleTrial.json"
)


@pytest.fixture(name="rows")
def _rows() -> dict[str, Transaction]:
    return {
        "pending": rule_trial_row("RECIBO ALBOR MOVIL"),
        "decided": rule_trial_row("fibra albor", classification=BusinessClassification.BUSINESS),
        "archived": rule_trial_row("ALBOR", state=TransactionLifecycleState.ARCHIVED),
        "other": rule_trial_row("OTRA COSA"),
    }


def test_it_finds_active_movements_anywhere_ignoring_case_and_splits_what_it_would_classify(
    rows: dict[str, Transaction],
) -> None:
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, "albor", rows)
    assert answer.outcome == "matched"
    assert answer.hits == ("pending", "decided")
    assert answer.pending == ("pending",)
    assert all(classification_rule_in_scope(rows[item], reaffirm=False) for item in answer.pending)


def test_nothing_found_is_an_answer_not_a_refusal(rows: dict[str, Transaction]) -> None:
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, "zzz", rows)
    assert (answer.outcome, answer.hits, answer.pending) == ("matched", (), ())


@pytest.mark.parametrize("pattern", ["", "   ", "\t"])
def test_a_blank_pattern_is_refused_as_the_writer_refuses_it(pattern: str, rows: dict[str, Transaction]) -> None:
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, pattern, rows)
    assert (answer.outcome, answer.hits) == ("empty_pattern", ())


@pytest.mark.parametrize("pattern", ["[unclosed", "(", "(?P<x", "*a"])
def test_a_broken_pattern_is_refused_as_the_writer_refuses_it(pattern: str, rows: dict[str, Transaction]) -> None:
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, pattern, rows)
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
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, pattern, {"row": rule_trial_row(description)})
    assert (answer.hits == ("row",)) is found
    assert bool(re.search(pattern, description, re.IGNORECASE)) is found


def test_every_recorded_answer_is_the_engines() -> None:
    recorded = json.loads(_RECORDING.read_text(encoding="utf-8"))
    assert recorded["answers"]
    for answer in recorded["answers"]:
        assert recorded_rule_trial_answer(recorded["descriptions"], answer["description_pattern"]) == answer


def test_the_number_the_window_recording_refuses_is_refused_and_its_correction_is_taken() -> None:
    # 91 is the control pair of this account; worked by hand, mod 97 of the moved digits is 1.
    assert iban_mod_97("ES9121000418450200051332") == 1
    assert iban_mod_97("ES9221000418450200051332") != 1


_CATASTROPHIC: Final = r"(a+)+$"


def test_a_pattern_that_overruns_is_answered_as_one_and_the_active_rows_are_all_it_saw() -> None:
    stuck = "a" * 27 + "!"
    answer = try_rule_pattern(RULE_TRIAL_PROFILE, _CATASTROPHIC, {"stuck": rule_trial_row(stuck)})
    assert (answer.outcome, answer.hits, answer.pending) == ("overrun", (), ())
    archived = {"stuck": rule_trial_row(stuck, state=TransactionLifecycleState.ARCHIVED)}
    assert try_rule_pattern(RULE_TRIAL_PROFILE, _CATASTROPHIC, archived).outcome == "matched"


@pytest.mark.parametrize("pattern", ["a{99999999999}", "(" * 1000 + ")" * 1000, "(?L)a"])
def test_every_way_a_pattern_cannot_compile_is_the_invalid_answer(pattern: str, rows: dict[str, Transaction]) -> None:
    assert try_rule_pattern(RULE_TRIAL_PROFILE, pattern, rows).outcome == "invalid_pattern"
    assert description_pattern_error(pattern) is not None
    with pytest.raises((ClassificationRuleError, ValueError)):
        LedgerClassificationRule.create(
            description_pattern=pattern, classification=BusinessClassification.BUSINESS, actor="t"
        )


def test_a_new_pattern_past_the_limit_is_too_long_yet_a_stored_rule_past_it_stays_readable(
    rows: dict[str, Transaction],
) -> None:
    longer = "albor|" + "x" * RULE_PATTERN_ENTRY_MAX_LENGTH
    assert try_rule_pattern(RULE_TRIAL_PROFILE, longer, rows).outcome == "too_long"
    stored = LedgerClassificationRule.create(
        description_pattern=longer, classification=BusinessClassification.BUSINESS, actor="t"
    )
    assert LedgerClassificationRule.model_validate(stored.model_dump(mode="python")) == stored
