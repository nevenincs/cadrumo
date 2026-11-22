"""The ``--fx-rate`` option reaches the registered request in the rate grammar, or refuses at the boundary.

A rate needs the fraction digits it has (``0.9250``), so it is not held to the
two-decimal euro-amount grammar. The bare Spanish thousands shape stays refused
rather than guessed. Whether the rate is above zero and the invoice foreign is
the worker's refusal, so ``0`` crosses the boundary unchanged.
"""

from __future__ import annotations

import pytest
import typer

from ....application.operations.public_scalar import PublicDecimal
from ..ledger_business_invoice_commands import _declared_fx_rate

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("typed", ["0.9250", "1.1712", "0.918273645", "0"])
def test_a_typed_rate_reaches_the_request_with_every_digit(typed: str) -> None:
    assert _declared_fx_rate(typed) == PublicDecimal(decimal=typed)


def test_an_omitted_rate_is_absent_from_the_request() -> None:
    assert _declared_fx_rate(None) is None


@pytest.mark.parametrize("typed", ["1.234", "0,9250", "1e-1", "NaN", "rate"])
def test_a_rate_outside_the_grammar_is_refused_naming_its_option(typed: str) -> None:
    with pytest.raises(typer.BadParameter) as refused:
        _declared_fx_rate(typed)

    assert "fx-rate" in str(refused.value)
