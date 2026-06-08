"""Parity and referential integrity tests for all registered modelo localization files."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_complete_registry_tree_locales_compile_and_validate_cleanly() -> None:
    """The entire registry tree's localization files must compile and validate without errors.

    Any malformed TOML structures or invalid translation keys referencing unknown
    casilla_ids/continuidad_ids will fail the loader's referential integrity checks
    and raise a RegistryValidationError.
    """
    root = bundled_path("registry", "aeat")

    # This loads all models and legal parameters, parsing and verifying every locales/*.toml file
    modelos, _catalogues = load_registry_tree(root)
    assert len(modelos) > 0, "No modelos loaded from registry"

    # Verify that M130 has our translations loaded
    m130 = next(m for m in modelos if str(m.id) == "130")
    revision = m130.revisions["2019-y-siguientes"]
    casilla_01 = next(c for c in revision.casillas if c.id == "01")

    # Assert labels loaded correctly for all three locales
    assert casilla_01.get_label("en") == "Income"
    assert casilla_01.get_label("ca") == "Ingressos"
    assert casilla_01.get_label("hu") == "Bevételek"

    # Assert help text loaded correctly
    assert casilla_01.get_help("en") == "Total cumulative business income for the tax year."
    assert casilla_01.get_help("ca") == "Ingressos acumulats de l'activitat econòmica."
    assert casilla_01.get_help("hu") == "Az adóévben elért összesített vállalkozási bevétel."
