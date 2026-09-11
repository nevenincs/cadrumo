"""Canonical supported-filing-year catalogue and advisory coverage tests."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.core.modelo import Modelo
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema import (
    SociedadesAnnualManualCoverageDisposition,
    SociedadesAnnualManualCoverageStatus,
    SupportedFilingYearsCatalogue,
)

from ..compiler.authority import compile_validated_authority
from ..compiler.loader import load_registry_tree, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_bundled_tree_declares_one_ordered_supported_year_catalogue() -> None:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    assert catalogues.supported_filing_years == SupportedFilingYearsCatalogue(
        years=(2022, 2023, 2024, 2025, 2026),
    )
    coverage = catalogues.sociedades_annual_manual_coverage
    assert coverage is not None
    assert tuple(disposition.year for disposition in coverage.dispositions) == catalogues.supported_filing_years.years
    assert tuple(disposition.status for disposition in coverage.dispositions) == (
        SociedadesAnnualManualCoverageStatus.AVAILABLE,
        SociedadesAnnualManualCoverageStatus.AVAILABLE,
        SociedadesAnnualManualCoverageStatus.AVAILABLE,
        SociedadesAnnualManualCoverageStatus.AVAILABLE,
        SociedadesAnnualManualCoverageStatus.UNPUBLISHED,
    )


@pytest.mark.parametrize("years", [(2025, 2024), (2025, 2025), (1999,), (2100,)])
def test_supported_year_declaration_refuses_noncanonical_year_sequences(years: tuple[int, ...]) -> None:
    with pytest.raises(ValidationError, match="supported filing years"):
        SupportedFilingYearsCatalogue(years=years)


@pytest.mark.parametrize(
    ("status", "source_ref", "acquisition_condition_key", "message"),
    [
        (SociedadesAnnualManualCoverageStatus.AVAILABLE, None, None, "requires source_ref"),
        (SociedadesAnnualManualCoverageStatus.UNACQUIRED, "manual-2022", "acquire it", "must not declare source_ref"),
        (SociedadesAnnualManualCoverageStatus.UNPUBLISHED, None, None, "requires acquisition_condition"),
    ],
)
def test_sociedades_manual_coverage_disposition_refuses_ambiguous_states(
    status: SociedadesAnnualManualCoverageStatus,
    source_ref: str | None,
    acquisition_condition_key: str | None,
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        SociedadesAnnualManualCoverageDisposition(
            year=2026,
            status=status,
            source_ref=source_ref,
            official_locator="https://example.com/aeat/manuals",
            observed_at=date(2026, 9, 10),
            acquisition_condition_key=acquisition_condition_key,
        )


def test_m303_annual_orden_projection_years_are_driven_by_registry_catalogue() -> None:
    authority = compile_validated_authority(bundled_path("registry", "aeat"), bundled_path())
    catalogue = authority.catalogues.supported_filing_years
    assert catalogue is not None

    orden = authority.catalogues.supplementary_ordenes[Modelo.M303]
    assert tuple(sorted({projection.ejercicio for projection in orden.projections})) == catalogue.years


def test_supported_year_declaration_is_fingerprinted_registry_data() -> None:
    declaration = bundled_path("registry", "aeat", "legal", "supported-filing-years.toml")

    assert isinstance(declaration, Path)
    assert declaration.is_file()


def test_shared_catalogue_refuses_missing_supported_year_declaration(tmp_path: Path) -> None:
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "empty.toml").write_text("", encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="missing supported_filing_years"):
        load_shared_catalogues(tmp_path)


def test_shared_catalogue_refuses_missing_sociedades_annual_manual_coverage(tmp_path: Path) -> None:
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "supported-filing-years.toml").write_text(
        "[supported_filing_years]\nyears = [2025]\n",
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="missing sociedades_annual_manual_coverage"):
        load_shared_catalogues(tmp_path)


def test_shared_catalogue_refuses_duplicate_supported_year_declarations(tmp_path: Path) -> None:
    declaration = "[supported_filing_years]\nyears = [2025]\n"
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "first.toml").write_text(declaration, encoding="utf-8")
    (legal_dir / "second.toml").write_text(declaration, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_shared_catalogues(tmp_path)


def _write_sociedades_coverage_fixture(
    tmp_path: Path,
    *,
    coverage_year: int = 2025,
    source_ref: str = "manual-2025",
    declared_source_ref: str | None = None,
    source_kind: str = "manual_pdf",
    source_authority: str = "aeat",
    corpus_path: str = "corpus/manuals/sociedades/2025/source.pdf",
    applies_from: str = "2025-01-01",
    applies_to: str = "2025-12-31",
) -> None:
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "supported-filing-years.toml").write_text(
        "[supported_filing_years]\nyears = [2025]\n",
        encoding="utf-8",
    )
    (legal_dir / "coverage.toml").write_text(
        "[sociedades_annual_manual_coverage]\n\n"
        "[[sociedades_annual_manual_coverage.dispositions]]\n"
        f"year = {coverage_year}\n"
        'status = "available"\n'
        f'source_ref = "{source_ref}"\n'
        'official_locator = "https://example.com/aeat/manual-2025.pdf"\n'
        "observed_at = 2026-09-10\n",
        encoding="utf-8",
    )
    source_id = declared_source_ref or source_ref
    (legal_dir / "source.toml").write_text(
        f'''[sources."{source_id}"]
evidence_tier = "official_source_guidance"
authority = "{source_authority}"
kind = "{source_kind}"
corpus_path = "{corpus_path}"
sha256 = "44f8354494a5ba03ba1792a8d3e9c534c47a9181980fde7a3f44b06ef2ae7c7f"
bytes = 1000
retrieved_at = 2026-09-10
applies_from = {applies_from}
applies_to = {applies_to}
source_url = "https://example.com/aeat/manual-2025.pdf"
review_status = "pending_review"
''',
        encoding="utf-8",
    )


def test_shared_catalogue_refuses_duplicate_sociedades_annual_manual_coverage(tmp_path: Path) -> None:
    _write_sociedades_coverage_fixture(tmp_path)
    (tmp_path / "legal" / "duplicate-coverage.toml").write_text(
        "[sociedades_annual_manual_coverage]\n\n"
        "[[sociedades_annual_manual_coverage.dispositions]]\n"
        "year = 2025\n"
        'status = "unpublished"\n'
        'official_locator = "https://example.com/aeat/manuals"\n'
        "observed_at = 2026-09-10\n"
        'acquisition_condition_key = "recheck"\n',
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="sociedades_annual_manual_coverage is already declared"):
        load_shared_catalogues(tmp_path)


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"coverage_year": 2024}, "must declare exactly the supported filing years"),
        ({"source_ref": "unknown-manual", "declared_source_ref": "manual-2025"}, "references unknown source"),
        ({"source_kind": "instructions"}, "must be kind='manual_pdf'"),
        ({"source_authority": "boe"}, "must be published by AEAT"),
        ({"corpus_path": "corpus/manuals/renta/2025/source.pdf"}, "must use corpus path"),
        ({"applies_to": "2026-01-01"}, "must have the exact annual applicability interval"),
    ],
)
def test_shared_catalogue_refuses_invalid_sociedades_annual_manual_source(
    tmp_path: Path,
    kwargs: dict[str, str | int],
    message: str,
) -> None:
    _write_sociedades_coverage_fixture(tmp_path, **kwargs)

    with pytest.raises(RegistryLoadError, match=message):
        load_shared_catalogues(tmp_path)
