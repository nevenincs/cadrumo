"""Modelo 115 registry behaviour for quarterly rental withholding filings."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .. import RegistryValidator, build_snapshot, load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")


def _load_modelo(modelo_id: str):
    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(item for item in modelos if item.id == modelo_id)
    return modelo, catalogues


def test_modelo_115_validated_snapshot_owns_workflow_surfaces() -> None:
    modelo, catalogues = _load_modelo("115")

    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)
    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=2026,
        period="1T",
    )

    assert snapshot.revision.orden_aplicabilidad == ("orden-2000-11-20:apartado-primero",)
    construct = snapshot.revision.constructs[0]
    linked_by_surface = {
        link.surface: link for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    assert {
        "calculation",
        "filing",
        "export",
        "verification",
        "review",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "deadline",
        "workflow",
    } <= set(linked_by_surface)
    assert all(link.requires_snapshot for link in linked_by_surface.values())
