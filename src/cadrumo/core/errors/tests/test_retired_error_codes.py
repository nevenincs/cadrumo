"""Every code a persisted record can hold stays readable after the catalogue retires it."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.errors.error_codes import (
    RETIRED_ERROR_CODE_SUCCESSORS,
    current_error_code,
    declared_error_codes_by_qualname,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_HISTORY = Path(__file__).with_name("declared_code_history.txt")
"""Append-only: every code the catalogue has declared, so a removal is seen rather than forgotten."""


def _history() -> list[str]:
    return [line for line in _HISTORY.read_text(encoding="utf-8").splitlines() if line]


def _declared() -> set[str]:
    return {error_code.code for error_code in declared_error_codes_by_qualname().values()}


def test_the_code_history_is_sorted_and_names_each_code_once() -> None:
    history = _history()
    assert history == sorted(set(history))


def test_every_declared_code_is_in_the_history() -> None:
    missing = sorted(_declared() - set(_history()))
    assert not missing, f"append these codes to {_HISTORY.name}, keeping it sorted: {missing}"


def test_a_code_that_left_the_catalogue_names_its_successor() -> None:
    """Journals, receipts and refusal evidence keep a code as long as they live, so none may vanish."""
    declared = _declared()
    vanished = sorted(code for code in _history() if code not in declared and code not in RETIRED_ERROR_CODE_SUCCESSORS)
    assert not vanished, (
        f"persisted records can hold {vanished}; name each one's successor in RETIRED_ERROR_CODE_SUCCESSORS"
    )


def test_a_retired_code_is_no_longer_declared_and_reads_as_a_declared_successor() -> None:
    declared = _declared()
    history = set(_history())
    for retired, successor in RETIRED_ERROR_CODE_SUCCESSORS.items():
        assert retired not in declared
        assert retired in history
        assert successor in declared
        assert current_error_code(retired) == successor


def test_a_declared_code_reads_as_itself() -> None:
    for code in _declared():
        assert current_error_code(code) == code
