"""Focused enrollment tests for authored facts backed by modelo supplements."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from shutil import copytree

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority
from cadrumo.domain.calculations.registry.lorca_reduction import resolve_lorca_reduction

from ..fact_providers import compile_registered_fact_providers
from ..loader import load_modelo_source, load_registry_tree
from ..loader_cache import discover_modelo_sources

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _modelo(modelo_id: str):
    sources = {
        source.modelo_id: source for source in discover_modelo_sources(bundled_path("registry", "aeat", "modelos"))
    }
    return load_modelo_source(sources[modelo_id])


def _copy_partial_tree(tmp_path: Path, modelo_id: str) -> Path:
    bundled_root = Path(bundled_path("registry", "aeat"))
    registry_root = tmp_path / "aeat"
    copytree(bundled_root / "facts", registry_root / "facts")
    copytree(bundled_root / "legal", registry_root / "legal")
    copytree(bundled_root / "modelos" / modelo_id, registry_root / "modelos" / modelo_id)
    return registry_root


def test_lorca_reduction_fact_is_enrolled_with_modelo_303() -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("303"),),
    )

    assert "liva-orden-lorca-reduction" in catalogue.facts


def test_lorca_reduction_fact_is_enrolled_in_the_complete_loaded_tree() -> None:
    _modelos, catalogues = load_registry_tree(Path(bundled_path("registry", "aeat")))

    assert "liva-orden-lorca-reduction" in catalogues.facts.facts


def test_complete_loaded_modelo_303_tree_enrolls_lorca_fact(tmp_path: Path) -> None:
    _modelos, catalogues = load_registry_tree(_copy_partial_tree(tmp_path, "303"))

    assert "liva-orden-lorca-reduction" in catalogues.facts.facts


def test_lorca_reduction_fact_is_absent_without_modelo_303() -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("131"),),
    )

    assert "liva-orden-lorca-reduction" not in catalogue.facts


def test_complete_loaded_partial_tree_preserves_modelo_fact_scope(tmp_path: Path) -> None:
    _modelos, catalogues = load_registry_tree(_copy_partial_tree(tmp_path, "131"))

    assert "liva-orden-lorca-reduction" not in catalogues.facts.facts


def test_lorca_applicability_across_declared_support_and_projection_boundaries() -> None:
    _, catalogues = load_registry_tree(Path(bundled_path("registry", "aeat")))
    support = catalogues.supported_filing_years
    assert support is not None
    authority = CandidateFactAuthority(catalogues.facts, support)
    fact = catalogues.facts.facts["liva-orden-lorca-reduction"]
    upper = support.hard_ceiling if support.hard_ceiling is not None else support.horizon
    years = tuple(range(support.floor, upper + 1))
    if support.hard_ceiling is None:
        years += (support.horizon + 1,)
    assert not support.admits_filing_year(support.floor - 1)
    if support.hard_ceiling is not None:
        assert not support.admits_filing_year(support.hard_ceiling + 1)
    for year in years:
        for month, day in ((1, 1), (12, 31)):
            coordinate = date(year, month, day)
            authored = [
                variant
                for variant in fact.variants
                if (variant.valid_from is None or variant.valid_from <= coordinate)
                and (variant.valid_to is None or coordinate <= variant.valid_to)
            ]
            if authored:
                reduction = resolve_lorca_reduction(effective_date=coordinate, authority=authority)
                assert reduction.ejercicio == year
                assert reduction.municipality == "Lorca"
                assert reduction.annex_scope == "ANEXO II"
                assert reduction.percentage == Decimal("20")
                assert reduction.calculation_periods == ("trimestral", "anual")
                assert (reduction.source_ref,) == authored[0].source_refs
            else:
                # The support envelope admits the request, but an explicitly
                # exercise-scoped provision is not renewed for a year it never
                # covered: the resolver refuses the coordinate outright rather
                # than projecting a neighbouring exercise onto it.
                with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
                    resolve_lorca_reduction(effective_date=coordinate, authority=authority)
