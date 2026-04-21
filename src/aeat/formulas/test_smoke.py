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
    """The default registry must expose every shipped ruleset.

    Wave 1 (#173) shipped two Modelo 130 rulesets (2024, 2025).
    Wave 2 (#183) added two Modelo 303 rulesets (2024, 2025).
    """
    from . import get_registry

    registry = get_registry()
    ruleset_ids = {r.ruleset_id for r in registry.rulesets}
    assert ruleset_ids == {
        "modelo_111.2025",
        "modelo_115.2025",
        "modelo_123.2025",
        "modelo_130.2024",
        "modelo_130.2025",
        "modelo_131.2025",
        "modelo_200.2024",
        "modelo_202.2025",
        "modelo_303.2024",
        "modelo_303.2025",
        "modelo_390.2025",
        "modelo_100.summary.2025",
    }


@pytest.mark.unit
def test_engine_is_instantiable() -> None:
    """:class:`Engine` is a plain class with no required construction args."""
    from . import Engine

    engine = Engine()
    assert engine is not None
