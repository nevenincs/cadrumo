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


@pytest.mark.parametrize("effective_date", (date(2022, 1, 1), date(2022, 12, 31)))
def test_lorca_reduction_fact_resolves_at_both_2022_boundaries(effective_date: date) -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("303"),),
    )
    authority = CandidateFactAuthority(catalogue)

    reduction = resolve_lorca_reduction(effective_date=effective_date, authority=authority)

    assert reduction.ejercicio == 2022
    assert reduction.municipality == "Lorca"
    assert reduction.annex_scope == "ANEXO II"
    assert reduction.percentage == Decimal("20")
    assert reduction.calculation_periods == ("trimestral", "anual")
    assert reduction.legal_ref == "orden-hfp-1335-2021:da-4-lorca-2022-reduction:lorca-2022-reduction"
    assert reduction.source_ref == "boe-orden-hfp-1335-2021-iva-authority"


@pytest.mark.parametrize("effective_date", (date(2021, 12, 31), date(2023, 1, 1)))
def test_lorca_reduction_fact_refuses_dates_adjacent_to_2022(effective_date: date) -> None:
    catalogue = compile_registered_fact_providers(
        Path(bundled_path("registry", "aeat")),
        modelos=(_modelo("303"),),
    )
    authority = CandidateFactAuthority(catalogue)

    with pytest.raises(RegistryValidationError, match="has no variant for the exact query context"):
        resolve_lorca_reduction(effective_date=effective_date, authority=authority)
