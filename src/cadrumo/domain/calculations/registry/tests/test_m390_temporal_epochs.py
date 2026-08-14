"""Modelo 390 source-grounded annual revision boundaries."""

from __future__ import annotations

from datetime import date

import pytest

from .._errors import NoRevisionForPeriodError
from .._temporal import select_revision
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("filing_year", [2022, 2023, 2024, 2025])
def test_m390_selects_the_exact_annual_epoch_and_own_record_design(filing_year: int) -> None:
    modelo, catalogues = _committed_modelo("390")

    revision = select_revision(modelo, filing_year=filing_year, period="0A")

    own_source_ref = f"aeat-dr-390-{filing_year}"
    assert revision.id == str(filing_year)
    assert revision.valid_from == date(filing_year, 1, 1)
    assert revision.valid_to == date(filing_year, 12, 31)
    assert revision.period_selector.years == (filing_year,)
    assert revision.source_refs.count(own_source_ref) == 1
    serialized_revision = revision.model_dump_json()
    assert own_source_ref in serialized_revision
    for other_year in {2022, 2023, 2024, 2025} - {filing_year}:
        assert f"aeat-dr-390-{other_year}" not in serialized_revision
    assert catalogues.sources[own_source_ref].record_design_epoch == str(filing_year)
    assert catalogues.sources[own_source_ref].applies_from == date(filing_year, 1, 1)
    assert catalogues.sources[own_source_ref].applies_to == date(filing_year, 12, 31)


@pytest.mark.parametrize("unsupported_year", [*range(2010, 2022), 2026])
def test_m390_refuses_years_without_enrolled_record_design_authority(unsupported_year: int) -> None:
    modelo, _catalogues = _committed_modelo("390")

    with pytest.raises(NoRevisionForPeriodError):
        select_revision(modelo, filing_year=unsupported_year, period="0A")


def test_m390_rdl_4_2024_is_confined_to_the_2024_epoch() -> None:
    modelo, _catalogues = _committed_modelo("390")
    provision = "real-decreto-ley-4-2024:art-1"

    assert provision in modelo.revisions["2024"].model_dump_json()
    for year in ("2022", "2023", "2025"):
        assert provision not in modelo.revisions[year].model_dump_json()


def test_m390_has_no_open_compatibility_revision() -> None:
    modelo, _catalogues = _committed_modelo("390")

    assert set(modelo.revisions) == {"2022", "2023", "2024", "2025"}


def test_m390_preserves_canonical_casilla_and_calculation_identities_across_epochs() -> None:
    modelo, _catalogues = _committed_modelo("390")
    baseline = modelo.revisions["2022"]

    for year in ("2023", "2024", "2025"):
        revision = modelo.revisions[year]
        assert {casilla.id for casilla in revision.casillas} == {casilla.id for casilla in baseline.casillas}
        assert {binding.id for binding in revision.bindings} == {binding.id for binding in baseline.bindings}
        assert {formula.id for formula in revision.formulas} == {formula.id for formula in baseline.formulas}
        assert {relation.id for relation in revision.relations} == {relation.id for relation in baseline.relations}
