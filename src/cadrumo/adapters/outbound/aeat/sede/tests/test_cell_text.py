"""The shared cell reader's contract, made executable rather than asserted in prose.

``cell_text`` replaced two five-line copies -- the declaraciones listbox
parser's ``_cell_text`` and the notifications table parser's ``_safe_cell``.
They read as divergent because one stripped and one did not, but both callers
build their cell lists with ``get_text(" ", strip=True)``, so the strip was a
no-op and the two were identical on every real input.

The consolidated helper KEEPS the strip. "Absent or empty" is its contract, and
an implementation that only satisfies it while every caller happens to
pre-strip is coupled to an invariant stated nowhere. These tests are what make
that a property of the helper rather than a claim in its docstring.
"""

from __future__ import annotations

import pytest

from .._adapter_utils import cell_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_a_present_cell_is_returned() -> None:
    assert cell_text(["a", "b", "c"], 1) == "b"


def test_a_missing_index_is_none() -> None:
    """``None`` means the column was not located on this page at all."""
    assert cell_text(["a"], None) is None


def test_an_index_past_the_end_is_none() -> None:
    """A short row is normal: AEAT omits trailing cells rather than blanking them."""
    assert cell_text(["a"], 5) is None


def test_an_empty_cell_is_none_not_empty_string() -> None:
    """Absent and blank collapse deliberately -- no caller distinguishes them."""
    assert cell_text(["a", "", "c"], 1) is None


def test_a_whitespace_only_cell_is_none() -> None:
    """The case the strip exists for.

    Currently unreachable through either caller, because both pre-strip with
    ``get_text(" ", strip=True)``. That is exactly why it is tested here: the
    contract must hold for a caller that arrives later without that habit, and
    a no-op today is only provably a no-op if the behaviour it would provide is
    pinned.
    """
    assert cell_text(["a", "   ", "c"], 1) is None


def test_surrounding_whitespace_is_stripped_from_a_real_value() -> None:
    """Same reason: the value is returned clean whether or not the caller pre-cleaned it."""
    assert cell_text(["  spaced  "], 0) == "spaced"


def test_a_negative_index_reads_from_the_end() -> None:
    """Documented, not endorsed.

    Neither original guarded against a negative index and neither caller can
    produce one -- both derive the index from a header lookup that yields
    ``None`` when absent. Pinned so the behaviour is a known quantity rather
    than a surprise if a future caller computes an index by arithmetic.
    """
    assert cell_text(["a", "b", "c"], -1) == "c"
