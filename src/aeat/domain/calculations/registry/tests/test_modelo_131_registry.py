"""Modelo 131 registry behaviour for objective-estimation instalment filings."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import ModeloDefinition, RegistryCatalogues, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_COMMON_SURFACES = {
    "approval",
    "calculation",
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
def modelo_131_registry():
    return _load_modelo("131")


@pytest.mark.parametrize(
    ("filing_year", "required_surfaces"),
    [
        (2023, _COMMON_SURFACES),
        (2024, _COMMON_SURFACES),
        (2025, _COMMON_SURFACES),
        (2026, _COMMON_SURFACES | {"deadline"}),
    ],
)
def test_modelo_131_validated_snapshot_owns_workflow_surfaces(
    modelo_131_registry: tuple[ModeloDefinition, RegistryCatalogues],
    filing_year: int,
    required_surfaces: set[str],
) -> None:
    modelo, catalogues = modelo_131_registry
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year,
        period="1T",
    )

    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert set(linked_by_surface) >= required_surfaces
    assert all(link.requires_snapshot for link in linked_by_surface.values())
