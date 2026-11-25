"""The IVA year matrix enumerates the published support envelope and classifies each year by reachable grade."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority, PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
from cadrumo.domain.calculations.registry.schema_references import TemporalProjectionDirection

from ..personas import QUARTERS
from ..year_matrix import (
    COORDINATES,
    M303,
    M390,
    M390_ANNUAL_PERIOD,
    ORACLE_BOXES,
    BoxResolutionError,
    YearMatrix,
    YearTier,
    build_year_matrix,
    classify_year,
    matrix_from_operation,
    reaches,
    resolve_casilla_ids,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_APPLICABILITY = RegistryAuthorityGrade.APPLICABILITY
_CALCULATION = RegistryAuthorityGrade.CALCULATION
_FILING = RegistryAuthorityGrade.FILING


def _grades(quarters: RegistryAuthorityGrade | list[RegistryAuthorityGrade], annual: RegistryAuthorityGrade):
    per_quarter = quarters if isinstance(quarters, list) else [quarters] * len(QUARTERS)
    grades = {(M303, quarter): grade for quarter, grade in zip(QUARTERS, per_quarter, strict=True)}
    grades[(M390, M390_ANNUAL_PERIOD)] = annual
    return grades


# ---- pure classification, on a small hand-built set of grades ---------------------------------------------------


def test_every_coordinate_at_filing_grade_is_the_full_tier() -> None:
    assert classify_year(_grades(_FILING, _FILING)) is YearTier.FULL


def test_annual_summary_at_calculation_grade_runs_the_quarters_and_calculates_the_summary() -> None:
    assert classify_year(_grades(_FILING, _CALCULATION)) is YearTier.M390_CALCULATION


def test_annual_summary_below_calculation_grade_is_an_expected_refusal() -> None:
    assert classify_year(_grades(_FILING, _APPLICABILITY)) is YearTier.M390_REFUSED


def test_one_quarter_below_filing_grade_limits_the_chain_to_calculation() -> None:
    quarters = [_FILING, _CALCULATION, _FILING, _FILING]
    assert classify_year(_grades(quarters, _FILING)) is YearTier.M303_CALCULATION_ONLY
    assert classify_year(_grades(quarters, _APPLICABILITY)) is YearTier.M303_CALCULATION_ONLY


def test_one_quarter_below_calculation_grade_cannot_run_a_chain() -> None:
    quarters = [_FILING, _FILING, _FILING, _APPLICABILITY]
    assert classify_year(_grades(quarters, _FILING)) is YearTier.M303_UNREACHABLE


def test_a_missing_coordinate_is_refused_rather_than_assumed() -> None:
    grades = _grades(_FILING, _FILING)
    del grades[(M390, M390_ANNUAL_PERIOD)]
    with pytest.raises(KeyError):
        classify_year(grades)


def test_the_authority_ladder_orders_the_grades() -> None:
    assert reaches(_FILING, _CALCULATION)
    assert reaches(_CALCULATION, _CALCULATION)
    assert not reaches(_APPLICABILITY, _CALCULATION)
    assert not reaches(_CALCULATION, _FILING)


def test_coordinates_are_the_four_quarters_and_the_annual_summary() -> None:
    assert (*((M303, quarter) for quarter in QUARTERS), (M390, M390_ANNUAL_PERIOD)) == COORDINATES


# ---- casilla number to id resolution -----------------------------------------------------------------------------


def test_numbers_resolve_to_their_ids_and_absent_numbers_are_reported() -> None:
    pairs = [("27", "iva.a"), ("78", "iva.b"), ("99", "iva.c")]
    resolved, missing = resolve_casilla_ids(pairs, ["78", "27", "110"])
    assert resolved == (("78", "iva.b"), ("27", "iva.a"))
    assert missing == ("110",)


def test_a_number_that_names_two_casillas_is_refused() -> None:
    with pytest.raises(BoxResolutionError, match="more than one casilla"):
        resolve_casilla_ids([("27", "iva.a"), ("27", "iva.b")], ["27"])


# ---- the real published authority --------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def authority_root() -> Path:
    """The directory of the published authority descriptor the product itself reads."""
    return bundled_authority_descriptor_path().parent


@pytest.fixture(scope="module")
def operation(authority_root: Path) -> Iterator[PinnedAuthorityOperation]:
    authority = IndexedRegistryAuthority(authority_root / "authority.current.json")
    try:
        with authority.operation() as leased:
            yield leased
    finally:
        authority.close()


@pytest.fixture(scope="module")
def matrix(authority_root: Path) -> YearMatrix:
    return build_year_matrix(authority_root)


def test_the_matrix_covers_exactly_the_support_envelope(
    operation: PinnedAuthorityOperation, matrix: YearMatrix
) -> None:
    assert matrix.years == tuple(operation.supported_filing_years().years)
    assert matrix.years
    assert matrix_from_operation(operation) == matrix


def _expected_tier(operation: PinnedAuthorityOperation, year: int) -> YearTier:
    """Derive the tier from the authority's own reachable grades, without the module under test."""
    quarters = [operation.reachable_authority_grade(M303, filing_year=year, period=quarter) for quarter in QUARTERS]
    annual = operation.reachable_authority_grade(M390, filing_year=year, period=M390_ANNUAL_PERIOD)
    if any(grade is _APPLICABILITY for grade in quarters):
        return YearTier.M303_UNREACHABLE
    if any(grade is not _FILING for grade in quarters):
        return YearTier.M303_CALCULATION_ONLY
    if annual is _FILING:
        return YearTier.FULL
    if annual is _CALCULATION:
        return YearTier.M390_CALCULATION
    return YearTier.M390_REFUSED


def test_each_year_tier_follows_the_reachable_grades(operation: PinnedAuthorityOperation, matrix: YearMatrix) -> None:
    for row in matrix.rows:
        assert row.tier is _expected_tier(operation, row.year), row.year
        for modelo, period in COORDINATES:
            record = row.record(modelo, period)
            assert record.reachable_grade is operation.reachable_authority_grade(
                modelo, filing_year=row.year, period=period
            )


def test_projection_never_reaches_filing_grade(matrix: YearMatrix) -> None:
    for row in matrix.rows:
        for record in row.records:
            if record.projection_direction is not TemporalProjectionDirection.AUTHORED:
                assert not reaches(record.reachable_grade, _FILING), (record.year, record.modelo, record.period)
            assert (record.authored_filing_year == record.year) is (
                record.projection_direction is TemporalProjectionDirection.AUTHORED
            )


def test_records_name_the_revision_the_authority_selects(
    operation: PinnedAuthorityOperation, matrix: YearMatrix
) -> None:
    for row in matrix.rows:
        for record in row.records:
            selected = operation.revision_for_context(record.modelo, filing_year=row.year, period=record.period)
            assert record.revision_id == str(selected.id)


def test_resolved_casilla_ids_carry_the_number_printed_in_the_revision(
    operation: PinnedAuthorityOperation, matrix: YearMatrix
) -> None:
    for row in matrix.rows:
        for record in row.records:
            revision = operation.revision_for_context(record.modelo, filing_year=row.year, period=record.period)
            numbers_by_id = {str(casilla.id): casilla.number for casilla in revision.casillas}
            assert {number for number, _ in record.casilla_ids} | set(record.unresolved_boxes) == set(
                ORACLE_BOXES[record.modelo]
            )
            for number, casilla_id in record.casilla_ids:
                assert numbers_by_id[casilla_id] == number
                assert record.casilla_id(number) == casilla_id
            for number in record.unresolved_boxes:
                with pytest.raises(BoxResolutionError):
                    record.casilla_id(number)


def test_newest_full_year_is_a_supported_full_year(matrix: YearMatrix) -> None:
    newest = matrix.newest_full_year()
    assert newest in matrix.years
    assert matrix.row(newest).tier is YearTier.FULL
    assert all(year <= newest for year in matrix.years_with_tier(YearTier.FULL))
