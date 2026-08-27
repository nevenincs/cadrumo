"""Canonical Modelo 210 Convenio registry snapshot fixture."""

import pytest

from ....core.resources import bundled_path
from ....domain.calculations.registry.convenio import load_convenio_authority
from ....domain.calculations.registry.loader import load_registry_tree
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.snapshot import build_snapshot


@pytest.fixture(scope="module")
def m210_snapshot() -> RegistrySnapshot:
    """Build the real M210 / 2025 / EVENT-1 ConvenioAuthority snapshot.

    The compile-only registry load projects the bundled treaty tree onto M210,
    keeping these assertions independent of unrelated modelo churn without
    replacing the authority with a hand-built stand-in.
    """

    root = bundled_path("registry", "aeat")
    modelos, catalogues = load_registry_tree(root)
    catalogues = catalogues.model_copy(update={"convenio": load_convenio_authority(root / "treaties")})
    modelo = next(modelo for modelo in modelos if modelo.id == "210")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="EVENT-1")


__all__ = ["m210_snapshot"]
