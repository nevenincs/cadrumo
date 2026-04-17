"""Public-surface smoke test for :mod:`aeat.formulas`."""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


@pytest.mark.unit
def test_every_public_name_imports() -> None:
    """Every name in ``aeat.formulas.__all__`` must resolve to an attribute."""
    module = importlib.import_module("aeat.formulas")
    for name in module.__all__:
        assert hasattr(module, name), name


@pytest.mark.unit
def test_registry_has_shipped_rulesets() -> None:
    """The default registry must expose the two Modelo-130 rulesets."""
    from . import get_registry

    registry = get_registry()
    assert len(registry.rulesets) == 2


@pytest.mark.unit
def test_engine_is_instantiable() -> None:
    """:class:`Engine` is a plain class with no required construction args."""
    from . import Engine

    engine = Engine()
    assert engine is not None
