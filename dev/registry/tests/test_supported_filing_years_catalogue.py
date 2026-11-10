"""Canonical supported-filing-year catalogue and advisory coverage tests."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path
from typing import Final, TypedDict

import pytest
from pydantic import ValidationError

from cadrumo.core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST
from cadrumo.core.modelo import Modelo
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.schema_catalogues import (
    SociedadesAnnualManualCoverageDisposition,
    SociedadesAnnualManualCoverageStatus,
)
from cadrumo.domain.calculations.registry.snapshot_globals import SupportedFilingYearsCatalogue
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from ..compiler.loader import load_registry_tree, load_shared_catalogues

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_FLOOR: Final = filing_year_envelope().floor
_HORIZON: Final = filing_year_envelope().horizon


class _SociedadesCoverageFixtureOverrides(TypedDict, total=False):
    """Typed overrides accepted by the invalid-coverage fixture cases."""

    coverage_year: int
    source_ref: str
    declared_source_ref: str
    source_kind: str
    source_authority: str
    corpus_path: str
    applies_from: str
    applies_to: str


def test_bundled_tree_declares_one_ordered_supported_year_catalogue() -> None:
    _modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))

    declared = tomllib.loads(
        bundled_path("registry", "aeat", "legal", "supported-filing-years.toml").read_text(encoding="utf-8")
    )["supported_filing_years"]
    horizon = declared["horizon"]
    floor = horizon - declared["filing_grade_years_before_horizon"]

    # The catalogue is the TOML's bounds, resolved once: its years run from the floor to the horizon.
    assert catalogues.supported_filing_years == SupportedFilingYearsCatalogue(floor=floor, horizon=horizon)
    assert catalogues.supported_filing_years.years == tuple(range(floor, horizon + 1))
    coverage = catalogues.sociedades_annual_manual_coverage
    assert coverage is not None
    assert tuple(disposition.year for disposition in coverage.dispositions) == catalogues.supported_filing_years.years
    # Every year's manual is published except the horizon's, which is not yet out.
    assert tuple(disposition.status for disposition in coverage.dispositions) == (
        *(SociedadesAnnualManualCoverageStatus.AVAILABLE for _ in range(floor, horizon)),
        SociedadesAnnualManualCoverageStatus.UNPUBLISHED,
    )


@pytest.mark.parametrize(
    "bounds",
    [
        pytest.param({"floor": _HORIZON, "horizon": _FLOOR}, id="horizon-precedes-floor"),
        pytest.param({"floor": FOUR_DIGIT_YEAR_FIRST - 1, "horizon": _HORIZON}, id="floor-below-range"),
        pytest.param({"floor": _FLOOR, "horizon": FOUR_DIGIT_YEAR_LAST + 1}, id="horizon-above-range"),
        pytest.param({"floor": _FLOOR, "horizon": _HORIZON, "hard_ceiling": _HORIZON - 1}, id="ceiling-below-horizon"),
        pytest.param({"years": filing_year_envelope().years}, id="retired-enumerated-key"),
    ],
)
def test_supported_year_declaration_refuses_noncanonical_bounds(bounds: dict[str, object]) -> None:
    """Every way of mis-stating the span fails closed, including the retired key.

    The enumerated ``years`` key is refused rather than ignored: a declaration
    written against the old shape would otherwise load with neither bound set
    and silently claim an empty span.
    """
    with pytest.raises(ValidationError):
        SupportedFilingYearsCatalogue.model_validate(bounds)


def test_supported_year_declaration_derives_its_span_from_its_bounds() -> None:
    catalogue = SupportedFilingYearsCatalogue(floor=_FLOOR, horizon=_HORIZON)

    assert catalogue.years == tuple(range(_FLOOR, _HORIZON + 1))
    assert not catalogue.admits_filing_year(_FLOOR - 1), "below the floor is outside what the product claims"
    assert catalogue.admits_filing_year(_FLOOR)
    assert catalogue.admits_filing_year(_HORIZON + 1), (
        "an absent hard ceiling leaves the span open above the horizon, because the newest "
        "declared revision carries forward into a year no revision names"
    )


def test_a_declared_hard_ceiling_closes_the_span_above_the_horizon() -> None:
    ceiling = _HORIZON + 2
    catalogue = SupportedFilingYearsCatalogue(floor=_FLOOR, horizon=_HORIZON, hard_ceiling=ceiling)

    assert catalogue.years == tuple(range(_FLOOR, _HORIZON + 1)), "the ceiling does not widen authored coverage"
    assert catalogue.admits_filing_year(ceiling)
    assert not catalogue.admits_filing_year(ceiling + 1)


def test_a_hard_ceiling_at_the_horizon_disables_forward_projection() -> None:
    catalogue = SupportedFilingYearsCatalogue(floor=_FLOOR, horizon=_HORIZON, hard_ceiling=_HORIZON)

    assert catalogue.admits_filing_year(_HORIZON)
    assert not catalogue.admits_filing_year(_HORIZON + 1)
    assert catalogue.projection_coordinate(_HORIZON) == _HORIZON
    assert catalogue.projection_coordinate(_HORIZON + 1) is None


@pytest.mark.parametrize(
    ("status", "source_ref", "acquisition_condition_key", "message"),
    [
        (SociedadesAnnualManualCoverageStatus.AVAILABLE, None, None, "requires source_ref"),
        (
            SociedadesAnnualManualCoverageStatus.UNACQUIRED,
            f"manual-{_FLOOR}",
            "acquire it",
            "must not declare source_ref",
        ),
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
            year=_HORIZON,
            status=status,
            source_ref=source_ref,
            official_locator="https://example.com/aeat/manuals",
            observed_at=date(_HORIZON, 9, 10),
            acquisition_condition_key=acquisition_condition_key,
        )


def test_m303_annual_orden_projection_years_are_driven_by_registry_catalogue(registry_authority) -> None:
    authority = registry_authority
    catalogue = authority.catalogues.supported_filing_years
    assert catalogue is not None

    orden = authority.catalogues.supplementary_ordenes[Modelo("303")]
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
        _single_year_declaration(),
        encoding="utf-8",
    )

    with pytest.raises(RegistryLoadError, match="missing sociedades_annual_manual_coverage"):
        load_shared_catalogues(tmp_path)


def test_shared_catalogue_refuses_duplicate_supported_year_declarations(tmp_path: Path) -> None:
    declaration = _single_year_declaration()
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "first.toml").write_text(declaration, encoding="utf-8")
    (legal_dir / "second.toml").write_text(declaration, encoding="utf-8")

    with pytest.raises(RegistryLoadError, match="already declared"):
        load_shared_catalogues(tmp_path)


def _single_year_declaration() -> str:
    """A supported-year declaration whose span is the horizon alone."""
    return f"[supported_filing_years]\nfloor = {_HORIZON}\nhorizon = {_HORIZON}\n"


def _write_sociedades_coverage_fixture(
    tmp_path: Path,
    *,
    coverage_year: int | None = None,
    source_ref: str | None = None,
    declared_source_ref: str | None = None,
    source_kind: str = "manual_pdf",
    source_authority: str = "aeat",
    corpus_path: str | None = None,
    applies_from: str | None = None,
    applies_to: str | None = None,
) -> None:
    coverage_year = _HORIZON if coverage_year is None else coverage_year
    source_ref = f"manual-{_HORIZON}" if source_ref is None else source_ref
    corpus_path = f"corpus/manuals/sociedades/{_HORIZON}/source.pdf" if corpus_path is None else corpus_path
    applies_from = date(_HORIZON, 1, 1).isoformat() if applies_from is None else applies_from
    applies_to = date(_HORIZON, 12, 31).isoformat() if applies_to is None else applies_to
    legal_dir = tmp_path / "legal"
    legal_dir.mkdir()
    (legal_dir / "supported-filing-years.toml").write_text(
        _single_year_declaration(),
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
        f"year = {_HORIZON}\n"
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
        ({"coverage_year": _HORIZON - 1}, "must declare exactly the supported filing years"),
        (
            {"source_ref": "unknown-manual", "declared_source_ref": f"manual-{_HORIZON}"},
            "references unknown source",
        ),
        ({"source_kind": "instructions"}, "must be kind='manual_pdf'"),
        ({"source_authority": "boe"}, "must be published by AEAT"),
        ({"corpus_path": f"corpus/manuals/renta/{_HORIZON}/source.pdf"}, "must use corpus path"),
        ({"applies_to": date(_HORIZON + 1, 1, 1).isoformat()}, "must have the exact annual applicability interval"),
    ],
)
def test_shared_catalogue_refuses_invalid_sociedades_annual_manual_source(
    tmp_path: Path,
    kwargs: _SociedadesCoverageFixtureOverrides,
    message: str,
) -> None:
    _write_sociedades_coverage_fixture(tmp_path, **kwargs)

    with pytest.raises(RegistryLoadError, match=message):
        load_shared_catalogues(tmp_path)
