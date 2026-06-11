"""Modelo 111 registry behaviour for withholding filings."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_REQUIRED_SURFACES = {
    "approval",
    "calculation",
    "deadline",
    "export",
    "extractor",
    "filing",
    "portal",
    "reconciliation",
    "review",
    "verification",
    "workflow",
}


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


@pytest.fixture(scope="module")
def modelo_111_registry():
    return _load_modelo("111")


@pytest.mark.parametrize("period", ["1T", "01"])
def test_modelo_111_validated_snapshot_owns_workflow_surfaces(
    modelo_111_registry: tuple[ModeloDefinition, RegistryCatalogues], period: str,
) -> None:
    modelo, catalogues = modelo_111_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period=period,
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= _REQUIRED_SURFACES
    assert all(link.requires_snapshot for link in linked_by_surface.values())
