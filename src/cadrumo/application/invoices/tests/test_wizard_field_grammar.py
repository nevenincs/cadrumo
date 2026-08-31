"""Canonical-grammar conformance for the invoice wizard's operator-typed numerics.

The wizard's taxable base and IVA percentage are hand-typed at an interactive
boundary, so both are judged by
:func:`~core.decimal.try_parse_canonical_decimal` rather than a bare
:class:`~decimal.Decimal` call. The base carries the two-fractional-digit euro
cap (so the Spanish thousands shape ``1.000`` refuses instead of becoming one
euro); the percentage is uncapped because the registry's declared rate slots are
the authority on which values exist.

See Also:
    :func:`~core.decimal.try_parse_canonical_decimal`
        The grammar both fields enforce.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ..creation_wizard import _validate_iva_rate, _validate_taxable_base, _WizardFieldError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Forms the bare constructor really does accept, asserted constructible in each
# test so the coverage proves a tightening rather than restating the constructor.
_CONSTRUCTOR_ACCEPTS = ("1e3", "1E3", "+140000", "1_000", ".5", "1.", "NaN", "-NaN", "Infinity", "-Infinity")


@pytest.mark.parametrize("raw", _CONSTRUCTOR_ACCEPTS)
def test_taxable_base_refuses_forms_the_bare_constructor_accepted(raw: str) -> None:
    assert isinstance(Decimal(raw), Decimal), raw

    with pytest.raises(_WizardFieldError) as excinfo:
        _validate_taxable_base(raw)

    assert excinfo.value.field == "taxable_base"
    assert "invalid decimal amount" in excinfo.value.reason


@pytest.mark.parametrize("raw", ["1.000", "1.0000", "36.500", "1.234,56", "not-decimal", "1 000"])
def test_taxable_base_refuses_thousands_and_over_precise_forms(raw: str) -> None:
    """The euro-cent cap is what makes ``1.000`` refuse instead of becoming one euro."""
    with pytest.raises(_WizardFieldError) as excinfo:
        _validate_taxable_base(raw)

    assert excinfo.value.reason == f"invalid decimal amount: {raw!r}"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("1000", Decimal("1000")), ("1234.56", Decimal("1234.56")), ("0", Decimal("0")), ("  12.5  ", Decimal("12.5"))],
)
def test_taxable_base_accepts_canonical_euro_amounts(raw: str, expected: Decimal) -> None:
    assert _validate_taxable_base(raw) == expected


def test_taxable_base_still_refuses_a_negative_with_its_own_reason() -> None:
    """A negative conforms to the grammar, so the domain refusal must stay separate."""
    with pytest.raises(_WizardFieldError) as excinfo:
        _validate_taxable_base("-1.00")

    assert excinfo.value.reason == "must not be negative"


@pytest.mark.parametrize("raw", ["2e1", "+21", "2_1", "NaN", "Infinity"])
def test_iva_rate_refuses_non_canonical_text_as_a_decimal_failure(raw: str) -> None:
    """A malformed token reports as a decimal failure, not "not a recognised percentage".

    Reaching the registry slot check with unparsed text produced a misleading
    refusal that blamed the rate table for what was a typing error.
    """
    assert isinstance(Decimal(raw), Decimal), raw

    with pytest.raises(_WizardFieldError) as excinfo:
        _validate_iva_rate(raw)

    assert excinfo.value.field == "iva_rate"
    assert "invalid decimal percentage" in excinfo.value.reason


def test_iva_rate_still_reports_an_unrecognised_but_well_formed_rate() -> None:
    """A conforming number outside the registry slots keeps the slot-table refusal."""
    with pytest.raises(_WizardFieldError) as excinfo:
        _validate_iva_rate("17")

    assert "not a recognised IVA percentage" in excinfo.value.reason


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_iva_rate_treats_absent_input_as_absent(raw: str | None) -> None:
    assert _validate_iva_rate(raw) is None


def test_iva_rate_accepts_a_declared_slot() -> None:
    assert _validate_iva_rate("21") == Decimal("21")
