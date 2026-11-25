"""Both income screens drop a row that declares nothing, judged by the larger of its gross amount and taxable base."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..ledger_impatriado_bindings import unsupported_ledger_impatriado_income_observations
from ..ledger_renta_income_bindings import unsupported_ledger_renta_income_observations
from . import unrouted_renta_quantity_screen_scenarios as scenarios
from .authored_editions import filing_year_envelope
from .published_authority import published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# A casilla no Modelo 130 binding targets, so a row the screen keeps is reported as unsupported.
_UNTARGETED_CASILLA = "99999"

_CASES = [
    pytest.param("0", None, False, id="zero-gross-no-base"),
    pytest.param("100", None, True, id="gross-only"),
    pytest.param("-100", None, True, id="negative-gross-only"),
    pytest.param("0", "0", False, id="zero-both"),
    pytest.param("0", "100", True, id="base-only"),
    pytest.param("100", "0", True, id="gross-above-zero-base"),
    pytest.param("-50", "0", False, id="base-lifts-negative-gross-to-zero"),
    pytest.param("0", "-5", False, id="gross-lifts-negative-base-to-zero"),
    pytest.param("-5", "-3", True, id="both-negative"),
]


class _ImpatriadoRow:
    def __init__(self, gross: str, base: str | None) -> None:
        self.target_casilla_id = _UNTARGETED_CASILLA
        self.gross_amount = Decimal(gross)
        self.taxable_base_amount = None if base is None else Decimal(base)


@pytest.mark.parametrize(("gross", "base", "declarable"), _CASES)
def test_the_renta_screen_keeps_only_a_row_that_declares_something(
    gross: str, base: str | None, declarable: bool
) -> None:
    revision = published_snapshot("130", filing_year=filing_year_envelope().horizon, period="1T").revision
    row = scenarios.Row(gross=gross, withheld="0", base=base)
    row.target_casilla_id = _UNTARGETED_CASILLA

    assert (unsupported_ledger_renta_income_observations(revision, [row]) == (row,)) is declarable


@pytest.mark.parametrize(("gross", "base", "declarable"), _CASES)
def test_the_impatriado_screen_keeps_only_a_row_that_declares_something(
    gross: str, base: str | None, declarable: bool
) -> None:
    revision = published_snapshot("130", filing_year=filing_year_envelope().horizon, period="1T").revision
    row = _ImpatriadoRow(gross, base)

    assert (unsupported_ledger_impatriado_income_observations(revision, [row]) == (row,)) is declarable
