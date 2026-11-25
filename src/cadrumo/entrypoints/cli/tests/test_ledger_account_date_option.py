"""The own-account date options pass through the shared ISO gate, not a looser parse."""

from __future__ import annotations

from datetime import date

import pytest
import typer

from cadrumo.tests.english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

from ..ledger_account_commands import date_option

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_absent_option_stays_absent() -> None:
    assert date_option(None, option="--opened-on") is None


def test_an_iso_date_parses() -> None:
    assert date_option("2026-01-15", option="--opened-on") == date(2026, 1, 15)


@pytest.mark.parametrize("raw", ["20260115", "2026-W03-4", "2026W034", "15/01/2026", "", "not-a-date"])
def test_a_spelling_the_standard_library_admits_or_a_non_iso_ordering_is_refused(raw: str) -> None:
    with pytest.raises(typer.BadParameter, match="--on needs a date as YYYY-MM-DD"):
        date_option(raw, option="--on")
