"""Cross-reference tests between :mod:`aeat.portals` and :mod:`aeat.models`."""

from __future__ import annotations

import pytest

from aeat.models import ModeloCode
from aeat.portals._categories import PortalCategory
from aeat.portals._registry import PORTAL_REGISTRY

pytestmark = pytest.mark.unit


_FILING_CENSUS_BORRADOR = {
    PortalCategory.FILING,
    PortalCategory.CENSUS,
    PortalCategory.BORRADOR,
}


def test_every_related_modelo_is_a_known_code() -> None:
    """Every non-``None`` ``related_modelo`` resolves inside :class:`ModeloCode`."""
    valid = set(ModeloCode)
    for metadata in PORTAL_REGISTRY.values():
        if metadata.related_modelo is None:
            continue
        assert metadata.related_modelo in valid


def test_every_related_modelo_binds_to_filing_family_category() -> None:
    """Only FILING / CENSUS / BORRADOR carry a ``related_modelo``."""
    for metadata in PORTAL_REGISTRY.values():
        if metadata.related_modelo is not None:
            assert metadata.category in _FILING_CENSUS_BORRADOR
        else:
            assert metadata.category not in _FILING_CENSUS_BORRADOR


def test_every_modelo_code_has_at_least_one_filing_or_census_portal() -> None:
    """Every :class:`ModeloCode` is backed by a FILING or CENSUS portal."""
    coverage = {code: [] for code in ModeloCode}
    for metadata in PORTAL_REGISTRY.values():
        if metadata.category in {PortalCategory.FILING, PortalCategory.CENSUS}:
            assert metadata.related_modelo is not None
            coverage[metadata.related_modelo].append(metadata)
    for code, portals in coverage.items():
        assert portals, f"modelo {code.value} is uncovered"


def test_modelo_037_is_the_only_retired_carve_out() -> None:
    """M037's FILING/CENSUS portals are all retired; every other modelo has ≥1 active."""
    for code in ModeloCode:
        portals = [
            m
            for m in PORTAL_REGISTRY.values()
            if m.category in {PortalCategory.FILING, PortalCategory.CENSUS} and m.related_modelo is code
        ]
        if code is ModeloCode.MODELO_037:
            assert all(not p.active for p in portals)
        else:
            assert any(p.active for p in portals)
