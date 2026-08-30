"""Cross-reference tests between portal metadata and registry definitions."""

from __future__ import annotations

import pytest

from ..categories import PortalCategory
from ..codes import Portal
from ..registry import PORTAL_REGISTRY, portals_for_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_modelo_portal_linkage_comes_from_registry() -> None:
    """Modelo filing linkage is resolved from committed registry data."""
    entries = portals_for_modelo("130")
    assert [entry.portal for entry in entries] == [Portal.PORTAL_M130_PAGO_FRACCIONADO_ED]


@pytest.mark.parametrize(
    ("modelo", "portal"),
    [
        ("190", Portal.PORTAL_M190_RESUMEN_TRABAJO),
        ("193", Portal.PORTAL_M193_RESUMEN_CAPITAL),
        ("200", Portal.PORTAL_M200_SOCIEDADES_ANUAL),
        ("202", Portal.PORTAL_M202_SOCIEDADES_FRACCIONADO),
        ("349", Portal.PORTAL_M349_INTRACOMUNITARIAS),
    ],
)
def test_modelo_public_enum_portal_links_resolve_from_registry(modelo: str, portal: Portal) -> None:
    entries = portals_for_modelo(modelo)
    assert portal in {entry.portal for entry in entries}


def test_registry_linked_portals_are_filing_dispatch_entries() -> None:
    """Registry-backed lookup exposes only filing or borrador portals."""
    entries = portals_for_modelo("130")
    assert entries
    assert all(entry.category in {PortalCategory.FILING, PortalCategory.BORRADOR} for entry in entries)


def test_portal_metadata_has_no_modelo_binding_field() -> None:
    """Portal entries do not expose a modelo binding field."""
    for metadata in PORTAL_REGISTRY.values():
        assert "modelo" not in metadata.model_dump(mode="json")


def test_retired_modelo_037_portal_is_not_registry_linked_for_filing() -> None:
    """Retired censo metadata does not imply filing-grade modelo support."""
    metadata = PORTAL_REGISTRY[Portal.PORTAL_M037_CENSAL_SIMPLIFICADA]
    assert metadata.active is False
    assert portals_for_modelo("037") == ()
