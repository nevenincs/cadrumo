"""The own-account date options pass through the shared ISO gate, not a looser parse."""

from __future__ import annotations

from datetime import date

import pytest
import typer

from cadrumo.tests.english_locale_fixture import english_locale_fixture

__all__ = ["english_locale_fixture"]

from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..ledger_account_commands import date_option

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon


def test_an_absent_option_stays_absent() -> None:
    assert date_option(None, option="--opened-on") is None


def test_an_iso_date_parses() -> None:
    assert date_option(f"{_YEAR}-01-15", option="--opened-on") == date(_YEAR, 1, 15)


@pytest.mark.parametrize("raw", [f"{_YEAR}0115", f"{_YEAR}-W03-4", f"{_YEAR}W034", f"15/01/{_YEAR}", "", "not-a-date"])
def test_a_spelling_the_standard_library_admits_or_a_non_iso_ordering_is_refused(raw: str) -> None:
    with pytest.raises(typer.BadParameter, match="--on needs a date as YYYY-MM-DD"):
        date_option(raw, option="--on")
