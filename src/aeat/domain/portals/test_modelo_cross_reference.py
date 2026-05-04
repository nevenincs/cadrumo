"""Cross-reference tests between portal metadata and registry definitions."""

from __future__ import annotations

import pytest

from ._categories import PortalCategory
from ._codes import Portal
from ._registry import PORTAL_REGISTRY, portals_for_modelo

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_modelo_portal_linkage_comes_from_registry() -> None:
    """Modelo filing linkage is resolved from committed registry data."""
    entries = portals_for_modelo("130")
    assert [entry.portal for entry in entries] == [Portal.PORTAL_M130_PAGO_FRACCIONADO_ED]


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
    """Retired census metadata does not imply filing-grade modelo support."""
    metadata = PORTAL_REGISTRY[Portal.PORTAL_M037_CENSAL_SIMPLIFICADA]
    assert metadata.active is False
    assert portals_for_modelo("037") == ()
