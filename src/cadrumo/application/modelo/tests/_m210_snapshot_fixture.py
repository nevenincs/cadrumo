"""Canonical Modelo 210 Convenio registry snapshot fixture."""

import pytest
from test_support.registry_authoring import load_registry_tree

from ....core.resources.bundled_data import bundled_path
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....tests.registry_snapshot import build_snapshot


@pytest.fixture(scope="module")
def m210_snapshot() -> RegistrySnapshot:
    """Build the real M210 / 2025 / EVENT-1 registry snapshot.

    Treaty consumers resolve their own canonical governed facts, so the
    snapshot need not retain the superseded treaty projection.
    """

    root = bundled_path("registry", "aeat")
    modelos, catalogues = load_registry_tree(root)
    modelo = next(modelo for modelo in modelos if modelo.id == "210")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="EVENT-1")


__all__ = ["m210_snapshot"]
