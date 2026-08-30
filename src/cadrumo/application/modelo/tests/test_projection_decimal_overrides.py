"""Canonical-grammar conformance for the projection ``--casilla`` override channel.

The projection service's casilla overrides are a calculation input channel, so
they carry the *uncapped* fractional posture of
:func:`cadrumo.application.modelo._calculate_input._decimal`: sub-cent precision
is legitimate because the AEAT fixed-width encoder rounds such a value to cents
with ``ROUND_HALF_UP`` per the AEAT Instrucciones. What the grammar refuses is
text whose numeric meaning is not what it appears.

See Also:
    :func:`~core.decimal.try_parse_canonical_decimal`
        The canonical grammar both channels enforce.
    :class:`~CalculationRevision`
        The stored revision whose casilla values these overrides feed.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from .._projection import ModeloProjectInvalidDecimalOverrideError, _decimal_overrides

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MESSAGE_KEY = "cli.app.modelo.work.casilla_not_decimal"

# Forms the bare ``Decimal`` constructor this replaced really does accept. Each
# is asserted constructible below so the test proves a genuine tightening rather
# than restating the constructor.
_CONSTRUCTOR_ACCEPTS_BUT_GRAMMAR_REFUSES = (
    "1e3",
    "1E3",
    "1e-2",
    "+140000",
    "1_000",
    ".5",
    "1.",
    "NaN",
    "-NaN",
    "sNaN",
    "Infinity",
    "-Infinity",
)

# Forms the constructor also rejects; they must refuse through the typed error
# rather than escaping as a raw InvalidOperation.
_ALSO_REFUSED = ("1.234,56", "36.500,00", "not-decimal", "", "   ", "1 000", "5%")


def _casilla(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="projection decimal override test casilla id")


def test_refuses_forms_the_bare_constructor_would_accept() -> None:
    for raw in _CONSTRUCTOR_ACCEPTS_BUT_GRAMMAR_REFUSES:
        assert isinstance(Decimal(raw), Decimal), raw
        with pytest.raises(ModeloProjectInvalidDecimalOverrideError):
            _decimal_overrides({_casilla("0226"): raw}, translated_message=_MESSAGE_KEY)


def test_refuses_malformed_text_through_the_typed_error() -> None:
    for raw in _ALSO_REFUSED:
        with pytest.raises(ModeloProjectInvalidDecimalOverrideError):
            _decimal_overrides({_casilla("0226"): raw}, translated_message=_MESSAGE_KEY)


def test_refusal_carries_the_key_value_and_message() -> None:
    with pytest.raises(ModeloProjectInvalidDecimalOverrideError) as excinfo:
        _decimal_overrides({_casilla("0226"): "1e3"}, translated_message=_MESSAGE_KEY)

    assert excinfo.value.translated_message == _MESSAGE_KEY
    assert excinfo.value.context == {"key": "0226", "value": "1e3"}


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("140000", Decimal("140000")),
        ("1234.56", Decimal("1234.56")),
        ("0", Decimal("0")),
        ("-1234.56", Decimal("-1234.56")),
        ("  1234.56  ", Decimal("1234.56")),
        # Sub-cent precision is a legitimate calculation input the export layer
        # rounds ROUND_HALF_UP to cents. The fractional digit count is NOT what
        # is capped -- what refuses is a Spanish thousands lookalike, so a
        # sub-cent value whose lead group cannot open a grouping run passes at
        # any precision. `2.345` used to sit here and no longer can: `2` is a
        # valid lead group, so that text is genuinely undecidable between two
        # euros thirty-four and two thousand three hundred forty-five.
        ("0.335", Decimal("0.335")),
        ("0.123456", Decimal("0.123456")),
    ],
)
def test_accepts_canonical_forms_including_sub_cent(raw: str, expected: Decimal) -> None:
    values = _decimal_overrides({_casilla("0226"): raw}, translated_message=_MESSAGE_KEY)
    assert values[_casilla("0226")] == expected


def test_preserves_the_exact_declared_precision() -> None:
    """The stored Decimal keeps its trailing zeros, so the value is not re-coerced."""
    values = _decimal_overrides({_casilla("0226"): "1200.50"}, translated_message=_MESSAGE_KEY)
    assert str(values[_casilla("0226")]) == "1200.50"
