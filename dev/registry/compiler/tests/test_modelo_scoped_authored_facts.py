"""Focused enrollment tests for authored facts backed by modelo supplements."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path

from ..fact_providers import compile_registered_fact_providers
from ..loader import load_modelo_source
from ..loader_cache import discover_modelo_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo(modelo_id: str):
    sources = {
        source.modelo_id: source
        for source in discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
    }
    return load_modelo_source(sources[modelo_id])


def test_lorca_reduction_fact_is_enrolled_with_modelo_303() -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("303"),),
    )

    assert "liva-orden-lorca-reduction" in catalogue.facts


def test_lorca_reduction_fact_is_absent_without_modelo_303() -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("131"),),
    )

    assert "liva-orden-lorca-reduction" not in catalogue.facts
