"""Boundary tests for the shared optional euro-amount CLI option gate.

Exercises the real :func:`optional_decimal_option` in
:mod:`cadrumo.entrypoints.cli._modelo_cli_support` — the single home for the
"optional operator-typed amount whose refusal names its own field" shape, now
consumed by the eight ``modelo work calculate`` shortcut amounts and the two
``preview-maritime-exemption`` amounts. No mocks, no stubs, no skips: every case
drives the real grammar and asserts a concrete accept or a real
:exc:`typer.BadParameter` refusal.

The gate previously ran a bare ``Decimal(raw)``, so each refused form below was
silently admitted as a real figure.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
import typer

from ....core.config import override_settings
from ....core.i18n import clear_output_language_cache
from .._modelo_cli_support import optional_decimal_option

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TRANSLATION_KEY = "cli.app.modelo.work.prestacion_inss_exenta_not_decimal"
_DEFAULT = "--prestacion-inss-exenta must be a decimal amount; received: {value}"

# Forms a bare ``Decimal(raw)`` accepted. ``1.000`` is the Spanish
# thousands-grouping shape that became ``Decimal("1.0")`` — a one-euro figure
# where the operator meant one thousand; ``1e3`` is scientific notation;
# ``+1200`` carries a leading sign; ``NaN``/``Infinity`` are non-finite; and
# ``1200.555`` exceeds euro-cent precision for a hand-typed amount.
_REFUSED = (
    "1.000",
    "1e3",
    "1E3",
    "1e-3",
    "+1200",
    "+1200.50",
    "NaN",
    "Infinity",
    "-Infinity",
    "1_000",
    ".5",
    "1.",
    "1200.555",
    "1.234,56",
    "1200,50",
    "not-decimal",
    "",
    "   ",
)

_ACCEPTED = (
    ("1200", Decimal("1200")),
    ("1200.50", Decimal("1200.50")),
    ("1200.5", Decimal("1200.5")),
    ("0", Decimal("0")),
    # A leading ``-`` still conforms: fields whose domain forbids a negative
    # amount keep reporting that through their own validator, so this gate does
    # not change which surface refuses.
    ("-1200.50", Decimal("-1200.50")),
    # Surrounding whitespace is stripped; the number itself is canonical.
    ("  1200.50  ", Decimal("1200.50")),
)


@pytest.fixture(autouse=True)
def _english_locale() -> object:
    """Pin output language to English so refusal rendering is deterministic."""
    with override_settings(cadrumo_output_language="en"):
        clear_output_language_cache()
        yield
    clear_output_language_cache()


@pytest.mark.parametrize("raw", _REFUSED)
def test_refuses_non_canonical_amount(raw: str) -> None:
    with pytest.raises(typer.BadParameter):
        optional_decimal_option(raw, translation_key=_TRANSLATION_KEY, default=_DEFAULT)


@pytest.mark.parametrize(("raw", "expected"), _ACCEPTED)
def test_accepts_canonical_amount(raw: str, expected: Decimal) -> None:
    assert optional_decimal_option(raw, translation_key=_TRANSLATION_KEY, default=_DEFAULT) == expected


def test_absent_value_stays_none() -> None:
    """An unsupplied option is absent, not invalid — the optional contract."""
    assert optional_decimal_option(None, translation_key=_TRANSLATION_KEY, default=_DEFAULT) is None


def test_refusal_echoes_what_the_operator_typed() -> None:
    """The refusal interpolates the raw value, per the instructive-refusal contract.

    Asserts the interpolation contract rather than catalogue prose: whichever
    per-field message a caller supplies, the operator must see the value that was
    rejected so the refusal is correctable.
    """
    with pytest.raises(typer.BadParameter) as exc_info:
        optional_decimal_option("1.000", translation_key=_TRANSLATION_KEY, default=_DEFAULT)
    assert "1.000" in str(exc_info.value)
