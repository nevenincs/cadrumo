"""Corpus coverage must not depend on the legacy extractor registry."""

from __future__ import annotations

import importlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_corpus_coverage_does_not_read_legacy_extractor_registry() -> None:
    """The deleted Python extractor registry is no longer corpus authority."""
    extractor_package = importlib.import_module("aeat.adapters.inbound.declaracion._extractors")

    assert not hasattr(extractor_package, "_REGISTERED_CLASSES")
    assert not hasattr(extractor_package, "_REGISTRY")
