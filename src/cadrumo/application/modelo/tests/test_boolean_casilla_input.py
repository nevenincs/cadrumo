"""Operator input for a boolean-declared casilla, on the real registry.

Modelo 100 declares 92 operator-supplied boolean casillas whose answer the engine
reads out of the NUMERIC map as ``0`` / ``1``. Two of them are read by live
formulas, so the encoding is not cosmetic: casilla ``0100`` is a multiplicative
operand of the art. 23.2 arrendamiento-de-vivienda reducción, meaning an
unsupplied flag arrives as zero and withholds the reducción without any refusal.

These tests exercise the real snapshot and the real validator rather than a
fixture revision, because the property under test is that the operator-facing
gate and the engine agree about which casillas may carry a value -- a fixture
that declares its own casilla could agree with itself while the shipped registry
still refused.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core import CasillaId, validated_casilla_id
from ....core.resources import resources
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from .._registry_helpers import validate_casilla_input_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = 2024
_PERIOD = "0A"
# The art. 23.2 reducción flag ("Marque con una X si el arrendamiento tiene
# derecho a reducción") and the rendimiento íntegro that feeds its base.
_REDUCCION_FLAG: CasillaId = validated_casilla_id("0100", surface="_REDUCCION_FLAG")
_REDUCCION_TARGET: CasillaId = validated_casilla_id("0150", surface="_REDUCCION_TARGET")
_RENDIMIENTO_INTEGRO: CasillaId = validated_casilla_id("0102", surface="_RENDIMIENTO_INTEGRO")
_TEXT_CASILLA: CasillaId = validated_casilla_id("0001", surface="_TEXT_CASILLA")
_NUMERIC_CASILLA: CasillaId = validated_casilla_id("0003", surface="_NUMERIC_CASILLA")


def _snapshot() -> RegistrySnapshot:
    return resources().modelos.authority.snapshot("100", filing_year=_YEAR, period=_PERIOD)


def _calculate(snapshot: RegistrySnapshot, inputs: dict[CasillaId, Decimal]) -> dict[CasillaId, Decimal]:
    """Run the real registry engine, resolving every non-casilla channel to zero.

    The channels are filled wholesale rather than one at a time so the test states
    one fact -- what the CASILLA inputs do -- instead of silently depending on
    which bindings the revision happens to declare this year.
    """
    revision = snapshot.revision
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_year_end": date(_YEAR, 12, 31)},
        binding_values={binding.id: Decimal(0) for binding in revision.bindings},
        enum_binding_values={
            "renta-2024-profile-tax-residence-ccaa": "madrid",
            "renta-2024-rental-reduccion-art-23-2-tier": "tier-50",
        },
        relation_values={relation.id: Decimal(0) for relation in revision.relations},
        date_binding_values={binding.id: date(1980, 1, 2) for binding in revision.bindings},
        text_inputs={},
    )
    return {observation.casilla_id: observation.value for observation in result.observations}


def test_boolean_casilla_is_declared_boolean_and_operator_supplied() -> None:
    """The premise the rest of the file rests on, read off the shipped registry."""
    casillas = {casilla.id: casilla for casilla in _snapshot().revision.casillas}

    assert casillas[_REDUCCION_FLAG].data_type == "boolean"
    assert casillas[_REDUCCION_FLAG].input_kind == "manual"


def test_operator_may_supply_a_boolean_casilla() -> None:
    """The gate accepts both encodings of a boolean-declared casilla."""
    revision = _snapshot().revision

    accepted = validate_casilla_input_ids(revision, {_REDUCCION_FLAG: Decimal("1")})

    assert accepted == {_REDUCCION_FLAG: Decimal("1")}
    assert validate_casilla_input_ids(revision, {_REDUCCION_FLAG: Decimal("0")}) == {_REDUCCION_FLAG: Decimal("0")}


def test_boolean_casilla_outside_zero_or_one_is_refused_instructively() -> None:
    """A value the engine would reject is named here, where the operator typed it."""
    with pytest.raises(RegistryValidationError) as exc_info:
        validate_casilla_input_ids(_snapshot().revision, {_REDUCCION_FLAG: Decimal("2")})

    # The accepted domain and the offending casilla are machine facts; the
    # sentence that used to carry them is catalogue-rendered now.
    context = exc_info.value.context
    assert context is not None
    assert context["accepted"] == "0,1"
    assert _REDUCCION_FLAG in str(context["casilla_ids"])
    assert context["values"] == "2"


def test_python_bool_stays_refused_on_the_casilla_channel() -> None:
    """The casilla channel carries Decimals only; a ``bool`` is still not one.

    Guards the direction this change must not drift in: a ``True`` reaching the
    numeric channel would render as ``1`` on an amount row, filing a figure the
    taxpayer never stated.
    """
    with pytest.raises(RegistryValidationError):
        validate_casilla_input_ids(_snapshot().revision, {_REDUCCION_FLAG: True})


def test_text_casilla_stays_refused_on_the_decimal_channel() -> None:
    """Accepting the boolean family must not accept every non-numeric family."""
    with pytest.raises(RegistryValidationError):
        validate_casilla_input_ids(_snapshot().revision, {_TEXT_CASILLA: Decimal("1")})


def test_numeric_casilla_keeps_its_unrestricted_domain() -> None:
    """The 0 / 1 restriction is scoped to the boolean family, not applied globally."""
    revision = _snapshot().revision

    assert validate_casilla_input_ids(revision, {_NUMERIC_CASILLA: Decimal("12000.25")}) == {
        _NUMERIC_CASILLA: Decimal("12000.25"),
    }


def test_reduccion_is_withheld_unset_and_reachable_when_the_flag_is_supplied() -> None:
    """The defect this change closes, stated as the engine's own behaviour.

    Asserts the WIRING rather than the reduced amount: that the flag is the thing
    standing between a declared arrendamiento and its reducción. Asserting the
    figure would only re-run the registry's own formula and would pass just as
    happily if the rate were wrong.
    """
    snapshot = _snapshot()
    base = {_RENDIMIENTO_INTEGRO: Decimal("10000")}

    withheld = _calculate(snapshot, dict(base))
    claimed = _calculate(snapshot, {**base, _REDUCCION_FLAG: Decimal("1")})

    assert withheld[_REDUCCION_FLAG] == Decimal("0"), "an unsupplied flag reaches the engine as zero"
    assert withheld[_REDUCCION_TARGET] == Decimal("0"), "so the reducción is silently withheld"
    assert claimed[_REDUCCION_FLAG] == Decimal("1")
    assert claimed[_REDUCCION_TARGET] > Decimal("0"), "supplying the flag makes the reducción reachable"
