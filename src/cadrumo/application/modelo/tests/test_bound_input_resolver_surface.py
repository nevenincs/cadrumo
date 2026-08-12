"""The application projector is the sole living bound-input resolver surface."""

from __future__ import annotations

import inspect

import pytest

from ....domain.calculations import registry
from ....domain.calculations.registry import _bindings
from .. import resolve_available_bound_inputs_by_casilla_id
from .. import _binding_resolution

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RESOLVER_SUFFIX = "bound_inputs_by_casilla_id"
_RETIRED_RESOLVER = "resolve_bound_inputs" + "_by_casilla_id"


def test_available_bound_input_projector_is_the_sole_resolver_surface() -> None:
    """Keep one public projector and prevent the strict dead surface returning."""
    application_resolvers = {
        name: member
        for name, member in inspect.getmembers(_binding_resolution, inspect.isfunction)
        if name.endswith(_RESOLVER_SUFFIX)
    }

    assert application_resolvers == {
        "resolve_available_bound_inputs_by_casilla_id": resolve_available_bound_inputs_by_casilla_id,
    }
    assert _RETIRED_RESOLVER not in vars(_bindings)
    assert _RETIRED_RESOLVER not in vars(registry)
    assert _RETIRED_RESOLVER not in _bindings.__all__
    assert _RETIRED_RESOLVER not in registry.__all__

