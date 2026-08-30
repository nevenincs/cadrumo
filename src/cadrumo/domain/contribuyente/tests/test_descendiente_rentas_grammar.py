"""The `--descendiente RENTAS=` flag parses the canonical euro grammar only.

A bare ``Decimal()`` read the Spanish thousands shape ``12.500`` as twelve euros
fifty: a factor-of-1000 misread, silent, and in the claiming direction. The real
figure breaches the Art. 58.1 ceiling and disqualifies the descendant; the
misread figure sits far below it and restores the full mínimo. The governing
decision on operator-typed amounts already required a loud refusal here, and
this pins that the flag now honours it.

Choosing the probe figure is the load-bearing decision in this module, and the
obvious choices are all blind:

* ``8.000`` against the Art. 58.1 ceiling of 8.000 shows nothing. The ceiling
  excludes only figures strictly ABOVE it, so 8.000 and 8,00 both leave the
  descendant eligible and the mínimo identical.
* ``1.800`` against the Art. 61 norma 2ª ceiling of 1.800 is blind for the same
  reason, one threshold along.

Two thresholds, two blind spots, one cause: a figure that sits exactly ON a
boundary cannot distinguish the two readings. ``12.500`` is used instead
because the readings genuinely diverge -- 12.500 breaches the ceiling and
yields no mínimo, 12,50 does not and yields the full tranche -- so the
assertions below fail if the misread ever returns.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.errors import ProfileAnswerTypeError
from ..descendant_facts import parse_descendiente_flag

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_BIRTH = "NACIMIENTO=2015-03-01"


def _rentas(token: str) -> Decimal | None:
    return parse_descendiente_flag(f"{_BIRTH},RENTAS={token}").rentas_anuales_euros


@pytest.mark.parametrize(
    "token",
    [
        "12.500",  # Spanish thousands: the outcome-diverging case
        "8.000",  # Spanish thousands at a ceiling
        "1.800",  # Spanish thousands at the other ceiling
        "1.234,56",  # Spanish thousands + comma decimal
        "1e3",  # scientific
        "+100",  # explicit sign
        "NaN",
        "Infinity",
    ],
)
def test_ambiguous_or_non_canonical_amounts_are_refused(token: str) -> None:
    """Every shape outside the accepted grammar refuses rather than being read."""
    with pytest.raises(ProfileAnswerTypeError):
        _rentas(token)


@pytest.mark.parametrize(("token", "expected"), [("12500", "12500"), ("12500.75", "12500.75"), ("0", "0")])
def test_canonical_amounts_are_accepted(token: str, expected: str) -> None:
    """The accepted grammar still parses, so the refusal is not a blanket one.

    Without this the refusals above would be equally satisfied by a parser that
    rejects everything, which would be a different defect rather than a fix.
    """
    assert _rentas(token) == Decimal(expected)


def test_the_two_readings_of_the_probe_figure_diverge_in_outcome() -> None:
    """Why 12.500 and not a threshold figure: the readings must disagree.

    This asserts the property the module's choice of probe rests on, rather
    than leaving it as a claim in the docstring. Against the Art. 58.1 ceiling
    of 8.000 euros, the intended reading is excluded and the misread reading is
    not -- so a regression reintroducing the misread changes the tax outcome
    and cannot pass unnoticed.
    """
    ceiling = Decimal("8000")
    intended = Decimal("12500")
    misread = Decimal("12.500")

    assert intended > ceiling
    assert not misread > ceiling


def test_a_negative_amount_is_refused_rather_than_clamped() -> None:
    """A negative figure refuses; clamping to zero would be the claiming direction."""
    with pytest.raises(ProfileAnswerTypeError):
        _rentas("-1")


def test_an_absent_rentas_key_stays_undeclared() -> None:
    """Absent is not zero: the predicate reads it as no figure declared."""
    assert parse_descendiente_flag(_BIRTH).rentas_anuales_euros is None
