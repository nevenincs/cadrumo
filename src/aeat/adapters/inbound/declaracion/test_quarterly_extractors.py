"""Fail-closed tests for legacy declaración extractor dispatch."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from . import DeclaracionParseError, registered_extractors
from ._errors import NoExtractorRegisteredError
from ._extractors import get_extractor
from ._schema import TemplateRevision

pytestmark = [
    pytest.mark.unit,
    pytest.mark.domain_inbound,
    pytest.mark.fixture_tier_l3,
]


def test_registry_dispatch_requires_registry_snapshot() -> None:
    """Extractor dispatch refuses legacy Python-registered model tables."""
    revision = TemplateRevision(modelo="TEST", año=2026, revision="registry-test")

    with pytest.raises(NoExtractorRegisteredError, match="validated registry snapshots"):
        get_extractor(revision)


def test_registered_extractors_requires_registry_snapshot() -> None:
    """Legacy registry inspection is disabled."""
    with pytest.raises(DeclaracionParseError, match="validated registry snapshots"):
        registered_extractors()


def test_model_specific_extractor_modules_are_deleted() -> None:
    """No per-model extractor modules remain under the dispatch package."""
    extractor_dir = Path(__file__).resolve().parent / "_extractors"

    assert sorted(path.name for path in extractor_dir.glob("modelo_*.py")) == []
    extractor_package = importlib.import_module("aeat.adapters.inbound.declaracion._extractors")
    assert not hasattr(extractor_package, "_REGISTERED_CLASSES")
    assert not hasattr(extractor_package, "_REGISTRY")
