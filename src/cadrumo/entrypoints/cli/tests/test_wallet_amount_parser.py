"""Canonical wallet amount parser accepts precise euro input."""

from __future__ import annotations

from decimal import Decimal

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_wallet_amount_refuses_non_canonical_forms() -> None:
    """The shared wallet amount parser refuses every non-canonical euro form.

    Each form is asserted to be one the bare ``Decimal`` constructor this
    replaced really does accept, so the test proves a genuine tightening rather
    than restating the constructor. The headline case is ``1.000``: previously it
    became ``Decimal("1.0")``, declaring a one-euro carry-forward balance for an
    operator who meant one thousand.
    """
    import typer as _typer

    from cadrumo.entrypoints.cli._modelo_iva_wallet_cli import _wallet_amount

    for raw in ("1.000", "1e3", "1E3", "+1200", "1_000", ".5", "1.", "NaN", "-NaN", "Infinity", "-Infinity"):
        assert isinstance(Decimal(raw), Decimal), raw
        with pytest.raises(_typer.BadParameter):
            _wallet_amount(raw)

    for raw in ("1.234,56", "36.500,00", "not-decimal", "1 200"):
        with pytest.raises(_typer.BadParameter):
            _wallet_amount(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1200", Decimal("1200")),
        ("1200.50", Decimal("1200.50")),
        ("0", Decimal("0")),
        ("  1200.50  ", Decimal("1200.50")),
        # A leading '-' still conforms so the domain's own non-negative refusal
        # stays the surface that reports a negative balance.
        ("-1200.50", Decimal("-1200.50")),
    ],
)
def test_wallet_amount_accepts_canonical_forms(raw: str, expected: Decimal) -> None:
    from cadrumo.entrypoints.cli._modelo_iva_wallet_cli import _wallet_amount

    assert _wallet_amount(raw) == expected
