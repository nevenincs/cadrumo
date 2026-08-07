"""The IVA-compensation casilla vocabulary has one declaration, not one per consumer.

The Modelo 303 compensation chain is read by the filed-history projection, by the
binding-prefill resolver, and by the domain carry-forward derivation policy. Each
used to declare its own private copy of the same tokens behind its own copy of the
same validating wrapper, so a casilla renamed on one side kept resolving on the
other and the surfaces could disagree about which value an operator's
compensation came from.
"""

from __future__ import annotations

from types import ModuleType

import pytest

from ....core import validated_casilla_id
from ....domain import iva_compensation as iva_compensation_policy
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

#: Every module that names a compensation casilla token: the two calculations
#: consumers and the domain carry-forward policy that decides the figures.
_TOKEN_NAMING_MODULES = (
    _binding_prefill,
    _iva_compensation_history,
    iva_compensation_policy,
)


def _authority_by_token() -> dict[str, str]:
    tokens: dict[str, str] = {}
    for name in _iva_compensation_casillas.__all__:
        value = getattr(_iva_compensation_casillas, name)
        if isinstance(value, str):
            tokens[value] = value
    return tokens


@pytest.mark.parametrize("module", _TOKEN_NAMING_MODULES, ids=lambda module: module.__name__.rsplit(".", 1)[-1])
def test_no_module_declares_a_second_object_for_an_authority_token(module: ModuleType) -> None:
    """A module naming a compensation casilla holds the authority's object, not a twin.

    Identity, not equality: two independently declared constants comparing equal
    today is exactly the state that drifted, because a rename applies to one and
    silently leaves the other resolving.

    This checks the drift property rather than an inventory of which module
    imports which constant. An inventory asserts something the code is free to
    change for good reasons -- a consumer that stops reading a casilla directly
    because a policy now derives it for them -- and it went stale for exactly
    that reason, reddening on a correct change while never noticing that the
    domain policy held its own twin of four of these tokens all along. A module
    that simply does not name a token is silent here; a module that names it
    with its own object fails.

    One blind spot, stated rather than papered over: CPython interns short
    string literals, so a twin declaration of the bare-numeric token
    ``M303_RESULTADO_FINAL_CASILLA`` ("71") is the SAME object as the
    authority's and passes this check. Identity cannot discriminate there for
    any owner; only the dotted registry ids are covered.
    """
    authority = _authority_by_token()
    named = {
        attribute: value for attribute, value in vars(module).items() if isinstance(value, str) and value in authority
    }

    assert named, "the module names no compensation casilla, so this parametrisation is vacuous"
    for attribute, value in named.items():
        assert value is authority[value], f"{module.__name__}.{attribute} is a second object for {value!r}"


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
