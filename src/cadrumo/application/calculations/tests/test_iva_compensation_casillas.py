"""The IVA-compensation casilla vocabulary has one declaration, not one per consumer.

The Modelo 303 compensation chain is read by the filed-history projection and by
the binding-prefill resolver. Each used to declare its own private copy of the
same seven constants behind its own copy of the same validating wrapper, so a
casilla renamed on one side kept resolving on the other and the two surfaces
could disagree about which value an operator's compensation came from.
"""

from __future__ import annotations

import pytest

from ....core import validated_casilla_id
from .. import _binding_prefill, _iva_compensation_casillas, _iva_compensation_history

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SHARED_M303_CONSTANTS = (
    "M303_RESULTADO_CASILLA",
    "M303_GENERADA_CASILLA",
    "M303_POSTERIOR_CASILLA",
    "M303_DISPONIBLE_CASILLA",
    "M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA",
    "M303_COMPENSACION_APLICADA_CASILLA",
    "M303_RESULTADO_FINAL_CASILLA",
)


@pytest.mark.parametrize("name", _SHARED_M303_CONSTANTS)
def test_both_consumers_read_the_same_authority_constant(name: str) -> None:
    """Each consumer's constant IS the authority's, not a copy that happens to match.

    Identity, not equality: two independently declared constants comparing equal
    today is exactly the state that drifted. Binding both consumers to one object
    makes a rename impossible to apply on one side only.
    """
    authoritative = getattr(_iva_compensation_casillas, name)

    assert getattr(_iva_compensation_history, f"_{name}") is authoritative
    assert getattr(_binding_prefill, f"_{name}") is authoritative


@pytest.mark.parametrize("name", (*_SHARED_M303_CONSTANTS, "M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA"))
def test_every_declared_constant_is_a_validated_casilla_id(name: str) -> None:
    """Each constant passes the canonical casilla-id validator."""
    value = getattr(_iva_compensation_casillas, name)

    assert validated_casilla_id(value, surface="test") == value


@pytest.mark.parametrize("malformed", ["", "   ", "x" * 200])
def test_malformed_tokens_are_refused_at_declaration(malformed: str) -> None:
    """A token that is not a casilla id fails loudly rather than resolving to nothing.

    The declaration helper runs at import time, so a malformed constant can
    never reach a compensation calculation.
    """
    with pytest.raises(RuntimeError):
        _iva_compensation_casillas.iva_compensation_casilla_id(malformed)


def test_authority_exports_exactly_the_shared_vocabulary() -> None:
    """The module's public surface is the compensation vocabulary and its validator."""
    assert set(_iva_compensation_casillas.__all__) == {
        *_SHARED_M303_CONSTANTS,
        "M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA",
        "M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA",
        "iva_compensation_casilla_id",
    }
