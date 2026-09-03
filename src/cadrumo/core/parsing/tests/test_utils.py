"""Real-behaviour tests for :mod:`cadrumo.core.parsing.utils`.

Contract under test, :func:`_parse_bool`:
* Recognised truthy tokens  → True
* Recognised falsy tokens   → False
* Absent / empty / unknown  → None  (caller picks fallback)

Contract under test, :func:`_enum_value`: this is the converged home of two
formerly independent, byte-identical private functions
(``application/workflow/engine_helpers.py::enum_value`` and
``domain/submission/preflight.py::_enum_value``), so its behaviour is now
load-bearing for both a workflow-stage status/finding read and a submission
preflight status/auth-provider-kind read.
"""

from __future__ import annotations

from enum import Enum, StrEnum

import pytest

from ..utils import _enum_value, _parse_bool

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _WireStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class _NumericTier(Enum):
    """An enum whose ``.value`` is NOT a string -- the discriminating case.

    Distinguishes this converged ``_enum_value`` from the unrelated, genuinely
    different ``_enum_value`` in ``application/aggregation/ledger_filing_snapshot.py``:
    that one falls back to ``str(value)`` (the enum's own repr, e.g.
    ``"_NumericTier.THREE"``) when ``.value`` is not itself a string, while
    this converged version stringifies ``.value`` directly (``"3"``). Both are
    internally consistent; they are not interchangeable, which is exactly why
    that third function was left unconverged.
    """

    THREE = 3


_RECOGNIZED_TOKENS: tuple[tuple[str, bool], ...] = (
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("1", True),
    ("yes", True),
    ("YES", True),
    ("y", True),
    ("Y", True),
    ("si", True),
    ("sí", True),
    ("SI", True),
    ("SÍ", True),
    # The Spanish affirmative had been half-supported: "si"/"sí" were
    # recognised while "s" -- the abbreviation the filing layer has always
    # accepted -- and "verdadero", the ordinary word, were not. A vocabulary
    # that takes one spelling of yes and not another is arbitrary from the
    # operator's side, and the missing spellings are exactly what a reader
    # then silently turned into "no".
    ("s", True),
    ("S", True),
    ("verdadero", True),
    ("VERDADERO", True),
    ("false", False),
    ("False", False),
    ("FALSE", False),
    ("0", False),
    ("no", False),
    ("NO", False),
    ("n", False),
    ("N", False),
    ("falso", False),
    ("FALSO", False),
)

_UNKNOWN_TOKENS: tuple[str | None, ...] = (
    None,
    "",
    " ",
    "   ",
    "\t",
    "maybe",
    "MAYBE",
    "2",
    "yes please",
)


def test_parse_bool_recognized_and_unknown_tokens() -> None:
    for raw, expected in _RECOGNIZED_TOKENS:
        assert _parse_bool(raw) is expected

    for raw in _UNKNOWN_TOKENS:
        assert _parse_bool(raw) is None


def test_enum_value_none_maps_to_empty_string() -> None:
    """An absent value never renders as the literal string ``"None"``.

    Every caller compares this output against a closed vocabulary of real
    wire tokens (a status code, a severity level); ``"None"`` would either
    silently match a hostile value or, more likely, silently match nothing
    and drop out of the vocabulary with no error.
    """
    assert _enum_value(None) == ""


def test_enum_value_reads_a_string_enum_member() -> None:
    assert _enum_value(_WireStatus.OPEN) == "open"
    assert _enum_value(_WireStatus.CLOSED) == "closed"


def test_enum_value_stringifies_a_non_string_enum_value() -> None:
    """The discriminator against the unconverged sibling in ``ledger_filing_snapshot.py``.

    ``getattr(value, "value", value)`` reads ``.value`` first and stringifies
    THAT -- ``"3"``, not the enum's own repr.
    """
    assert _enum_value(_NumericTier.THREE) == "3"


def test_enum_value_passes_through_a_non_enum_value_via_str() -> None:
    assert _enum_value("already-a-string") == "already-a-string"
    assert _enum_value(42) == "42"
    assert _enum_value(True) == "True"
