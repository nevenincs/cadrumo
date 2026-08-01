"""Predicate dates are read through the canonical parsing contract.

The advisory that reads an acquisition-date casilla used to loop its own
``strptime`` format list, which accepted under-specified entries like
``1/2/2024`` and ``2024-2-9`` that the canonical
:func:`core.parsing.parse_date` refuses. The value decides a deduction's
eligibility against a statutory cutoff (LIRPF DT 18ª), so resolving a
partially-typed date to a specific day is acting on a date the operator never
stated.

The contract these pin: whatever the canonical parser refuses, the predicate
refuses too -- returning ``None`` so the advisory reports "no eligibility
signal" rather than a guess.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.parsing import parse_date
from .._verification_predicates import _parse_predicate_date

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Forms an operator or the registry cutoff literal legitimately uses.
ACCEPTED = {
    "2024-02-09": date(2024, 2, 9),
    "01/02/2024": date(2024, 2, 1),
    "01-02-2024": date(2024, 2, 1),
}

#: Under-specified entries: a date the operator has not fully stated.
UNDER_SPECIFIED = ("1/2/2024", "2024-2-9", "1-2-2024")


@pytest.mark.parametrize(("raw", "expected"), ACCEPTED.items())
def test_well_formed_dates_still_parse(raw: str, expected: date) -> None:
    assert _parse_predicate_date(raw) == expected


@pytest.mark.parametrize("raw", UNDER_SPECIFIED)
def test_under_specified_dates_yield_no_eligibility_signal(raw: str) -> None:
    """The audit's own probe values: previously resolved, now refused."""
    assert _parse_predicate_date(raw) is None


@pytest.mark.parametrize("raw", ["", "   ", "not-a-date", "2024-13-01", "32/01/2024", "9/9/24"])
def test_blank_and_invalid_values_remain_no_signal(raw: str) -> None:
    assert _parse_predicate_date(raw) is None


@pytest.mark.parametrize(
    "raw",
    [*ACCEPTED, *UNDER_SPECIFIED, "", "   ", "not-a-date", "2024-13-01", "32/01/2024", "9/9/24", "20240102"],
)
def test_predicate_never_accepts_what_the_canonical_parser_refuses(raw: str) -> None:
    """The invariant, stated as a relation rather than a value table.

    A future format added to the canonical contract flows through here; a
    format the canonical contract drops cannot survive here.
    """
    canonical: date | None = None
    text = raw.strip()
    if text:
        for fmt in ("iso8601", "ddmmyyyy"):
            canonical = parse_date(text, fmt=fmt, on_error="none")
            if canonical is not None:
                break

    assert _parse_predicate_date(raw) == canonical, raw
