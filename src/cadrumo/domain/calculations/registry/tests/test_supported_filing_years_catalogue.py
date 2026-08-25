"""Canonical supported-filing-year catalogue and advisory coverage tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from .....core.resources import bundled_path
from .._authority import ValidatedRegistryAuthority
from ..errors import RegistryLoadError
from .._loader import _load_shared_catalogue_files, load_registry_tree
from .._schema import SupportedFilingYearsCatalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_bundled_tree_declares_one_ordered_supported_year_catalogue() -> None:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    assert catalogues.supported_filing_years == SupportedFilingYearsCatalogue(
        years=(2022, 2023, 2024, 2025, 2026),
    )


@pytest.mark.parametrize("years", [(2025, 2024), (2025, 2025), (1999,), (2100,)])
def test_supported_year_declaration_refuses_noncanonical_year_sequences(years: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError, match="supported filing years"):
        SupportedFilingYearsCatalogue(years=years)


def test_authority_surfaces_advisory_gaps_with_complete_coordinates() -> None:
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )

    gaps = authority.supported_filing_year_gaps

    assert gaps
    assert all(gap.modelo and gap.filing_year and gap.period and gap.missing_prerequisite for gap in gaps)
    assert any(
        gap.modelo == "036"
        and gap.filing_year == 2022
        and gap.period == "alta"
        and gap.missing_prerequisite == "law-resolvable revision"
        for gap in gaps
    )


def test_m303_annual_orden_projection_years_are_driven_by_registry_catalogue() -> None:
    authority = ValidatedRegistryAuthority.load(
        bundled_path("registry", "aeat"),
        source_root=bundled_path(),
    )
    catalogue = authority.catalogues.supported_filing_years
    assert catalogue is not None

    orden = authority.catalogues.supplementary_ordenes["303"]
    assert tuple(sorted({projection.ejercicio for projection in orden.projections})) == catalogue.years


def test_supported_year_declaration_is_fingerprinted_registry_data() -> None:
    declaration = bundled_path("registry", "aeat", "legal", "supported-filing-years.toml")

    assert isinstance(declaration, Path)
    assert declaration.is_file()


def test_shared_catalogue_refuses_missing_supported_year_declaration(tmp_path: Path) -> None:
    (tmp_path / "empty.toml").write_text("", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="missing supported_filing_years"):
        _load_shared_catalogue_files(tmp_path)


def test_shared_catalogue_refuses_duplicate_supported_year_declarations(tmp_path: Path) -> None:
    declaration = "[supported_filing_years]\nyears = [2025]\n"
    (tmp_path / "first.toml").write_text(declaration, encoding="utf-8")
    (tmp_path / "second.toml").write_text(declaration, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="already declared"):
        _load_shared_catalogue_files(tmp_path)
