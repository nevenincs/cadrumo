"""Cross-reference tests between :mod:`aeat.models` and :mod:`aeat.portals`."""

from __future__ import annotations

import pytest

from ..portals._codes import Portal
from ..portals._registry import PORTAL_REGISTRY
from ._codes import ModeloCode
from ._registry import MODELO_REGISTRY

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_every_modelo_has_a_submission_portal() -> None:
    """Every v1 modelo binds to a typed :class:`Portal` member."""
    for code, metadata in MODELO_REGISTRY.items():
        assert metadata.submission_portal is not None, f"modelo {code.value} missing submission_portal"
        assert isinstance(metadata.submission_portal, Portal)


def test_submission_portal_resolves_in_portal_registry() -> None:
    """``submission_portal`` always resolves inside :data:`PORTAL_REGISTRY`."""
    for metadata in MODELO_REGISTRY.values():
        portal = metadata.submission_portal
        assert portal is not None
        assert portal in PORTAL_REGISTRY


def test_submission_portal_round_trips_related_modelo() -> None:
    """The portal's ``related_modelo`` equals the modelo's own code."""
    for code, metadata in MODELO_REGISTRY.items():
        portal = metadata.submission_portal
        assert portal is not None
        portal_metadata = PORTAL_REGISTRY[portal]
        assert portal_metadata.related_modelo is code


def test_submission_portal_is_filing_family_category() -> None:
    """Every bound portal is in the FILING / CENSUS family of categories."""
    from ..portals._categories import PortalCategory

    allowed = {PortalCategory.FILING, PortalCategory.CENSUS}
    for metadata in MODELO_REGISTRY.values():
        portal = metadata.submission_portal
        assert portal is not None
        portal_metadata = PORTAL_REGISTRY[portal]
        assert portal_metadata.category in allowed


def test_modelo_037_submission_portal_is_retired() -> None:
    """Modelo 037 binds to an ``active=False`` portal (the sole carve-out)."""
    metadata = MODELO_REGISTRY[ModeloCode.MODELO_037]
    assert metadata.submission_portal is Portal.PORTAL_M037_CENSAL_SIMPLIFICADA
    portal_metadata = PORTAL_REGISTRY[metadata.submission_portal]
    assert portal_metadata.active is False
