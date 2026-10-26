"""The invoice validation pass answers a question once, and only within its bounds.

These tests isolate the memo's own logic, so the governed-fact authorities are
minimal stand-ins: what is under test is which answers the pass reuses, not
what any authority resolves.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Final

import pytest

from ....core.time.clock import frozen_clock
from ...calculations.registry.facts.resolution import GovernedFactQuery, ResolvedGovernedFact
from ...calculations.registry.governed_fact_scope import validating_governed_facts
from ...calculations.registry.schema_references import TemporalSupportEnvelope
from .._validation_pass import answer_once, invoice_validation_pass

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Authority:
    """A distinct governed-fact source; the memo only ever compares identities."""

    def resolve_governed_fact(self, query: GovernedFactQuery) -> ResolvedGovernedFact:
        raise AssertionError(f"the memo must never resolve a fact itself: {query!r}")

    def supported_filing_years(self) -> TemporalSupportEnvelope:
        raise AssertionError("the memo must never read the support envelope")


class _Counter:
    """A deterministic projection that records how often it was asked."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def __call__(self, slot: str, on: date) -> tuple[str, date]:
        self.calls.append((slot, on))
        return slot, on


_ON: Final = date(2024, 12, 31)


def test_outside_a_pass_every_question_is_asked() -> None:
    counter = _Counter()
    with validating_governed_facts(_Authority()):
        answer_once(counter, "RATE_2", _ON)
        answer_once(counter, "RATE_2", _ON)

    assert len(counter.calls) == 2


def test_without_an_authority_in_scope_every_question_is_asked() -> None:
    counter = _Counter()
    with invoice_validation_pass():
        answer_once(counter, "RATE_2", _ON)
        answer_once(counter, "RATE_2", _ON)

    assert len(counter.calls) == 2


def test_inside_a_pass_an_identical_question_is_answered_once() -> None:
    counter = _Counter()
    with validating_governed_facts(_Authority()), invoice_validation_pass():
        first = answer_once(counter, "RATE_2", _ON)
        second = answer_once(counter, "RATE_2", _ON)

    assert first == second == ("RATE_2", _ON)
    assert counter.calls == [("RATE_2", _ON)]


def test_a_different_date_or_argument_is_a_different_question() -> None:
    counter = _Counter()
    with validating_governed_facts(_Authority()), invoice_validation_pass():
        answer_once(counter, "RATE_2", _ON)
        answer_once(counter, "RATE_2", date(2025, 1, 1))
        answer_once(counter, "RATE_7.5", _ON)
        answer_once(counter, slot="RATE_2", on=_ON)

    assert counter.calls == [("RATE_2", _ON), ("RATE_2", date(2025, 1, 1)), ("RATE_7.5", _ON), ("RATE_2", _ON)]


def test_an_answer_is_never_served_under_another_authority() -> None:
    counter = _Counter()
    first, second = _Authority(), _Authority()
    with invoice_validation_pass():
        with validating_governed_facts(first):
            answer_once(counter, "RATE_2", _ON)
        with validating_governed_facts(second):
            answer_once(counter, "RATE_2", _ON)
        with validating_governed_facts(first):
            answer_once(counter, "RATE_2", _ON)

    assert len(counter.calls) == 2


def test_nothing_is_kept_once_the_outermost_pass_ends() -> None:
    counter = _Counter()
    with validating_governed_facts(_Authority()):
        with invoice_validation_pass():
            with invoice_validation_pass():
                answer_once(counter, "RATE_2", _ON)
            answer_once(counter, "RATE_2", _ON)
        with invoice_validation_pass():
            answer_once(counter, "RATE_2", _ON)

    assert len(counter.calls) == 2


def test_a_pass_straddling_midnight_asks_again() -> None:
    """Projections defaulting to today must not reuse yesterday's answer."""
    counter = _Counter()
    with validating_governed_facts(_Authority()), invoice_validation_pass():
        with frozen_clock(datetime(2026, 3, 1, 22, 30, tzinfo=UTC)):
            answer_once(counter, "RATE_21", _ON)
        with frozen_clock(datetime(2026, 3, 1, 23, 30, tzinfo=UTC)):
            answer_once(counter, "RATE_21", _ON)

    assert len(counter.calls) == 2


def test_a_refusal_is_raised_afresh_every_time() -> None:
    attempts: list[str] = []

    def refuse(slot: str) -> str:
        attempts.append(slot)
        raise ValueError(f"{slot} refused attempt {len(attempts)}")

    with validating_governed_facts(_Authority()), invoice_validation_pass():
        with pytest.raises(ValueError, match="attempt 1"):
            answer_once(refuse, "RATE_2")
        with pytest.raises(ValueError, match="attempt 2"):
            answer_once(refuse, "RATE_2")

    assert attempts == ["RATE_2", "RATE_2"]
