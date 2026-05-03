"""Modelo 130 legacy extractor deletion gate."""

from __future__ import annotations

import importlib.util

import pytest

from ._errors import NoExtractorRegisteredError
from ._extractors import get_extractor
from ._schema import TemplateRevision

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound, pytest.mark.fixture_tier_l3]


def test_modelo_130_python_extractor_is_deleted() -> None:
    """Modelo 130 extraction must not resolve to the deleted Python module."""
    spec = importlib.util.find_spec("aeat.adapters.inbound.declaracion._extractors.modelo_130_v2025")
    assert spec is None

    revision = TemplateRevision(modelo="130", año=2025, revision="2025.01")
    with pytest.raises(NoExtractorRegisteredError, match="validated registry snapshots"):
        get_extractor(revision)
