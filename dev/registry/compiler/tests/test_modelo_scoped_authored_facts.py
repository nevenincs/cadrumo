"""Focused enrollment tests for authored facts backed by modelo supplements."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.lorca_reduction import resolve_lorca_reduction

from ..fact_providers import compile_registered_fact_providers
from ..loader import load_modelo_source
from ..loader_cache import discover_modelo_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo(modelo_id: str):
    sources = {
        source.modelo_id: source for source in discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
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


def test_lorca_reduction_fact_resolves_only_for_the_2022_filing_year() -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("303"),),
    )
    authority = CandidateFactAuthority(catalogue)

    reduction = resolve_lorca_reduction(effective_date=date(2022, 12, 31), authority=authority)

    assert reduction.ejercicio == 2022
    assert reduction.municipality == "Lorca"
    assert reduction.annex_scope == "ANEXO II"
    assert reduction.percentage == Decimal("20")
    assert reduction.calculation_periods == ("trimestral", "anual")
    assert reduction.legal_ref == "orden-hfp-1335-2021:da-4-lorca-2022-reduction:lorca-2022-reduction"
    assert reduction.source_ref == "boe-orden-hfp-1335-2021-iva-authority"

    for outside_window in (date(2021, 12, 31), date(2023, 1, 1)):
        with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
            resolve_lorca_reduction(effective_date=outside_window, authority=authority)
