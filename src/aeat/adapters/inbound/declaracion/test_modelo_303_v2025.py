"""Modelo 303 legacy extractor deletion gate."""

from __future__ import annotations

import importlib.util

import pytest

from ._errors import NoExtractorRegisteredError
from ._extractors import get_extractor
from ._schema import TemplateRevision

pytestmark = [pytest.mark.unit, pytest.mark.domain_inbound, pytest.mark.fixture_tier_l3]


def test_modelo_303_python_extractors_are_deleted() -> None:
    """Modelo 303 extraction must not resolve to deleted Python modules."""
    assert importlib.util.find_spec("aeat.adapters.inbound.declaracion._extractors.modelo_303_v2025") is None
    assert importlib.util.find_spec("aeat.adapters.inbound.declaracion._extractors.modelo_303_v2024_09") is None

    revision = TemplateRevision(modelo="303", año=2025, revision="2025.01")
    with pytest.raises(NoExtractorRegisteredError, match="validated registry snapshots"):
        get_extractor(revision)
