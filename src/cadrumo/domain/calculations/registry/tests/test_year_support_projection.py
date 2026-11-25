"""A dated record's facts reach below the support floor as a projection, and filing stays gated.

Every year here derives from the published envelope, except the dates of
Real Decreto-ley 20/2012 art. 23, where the fixed date is the point of the case.
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from .....core.filing_year import FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST, FilingYear
from .....core.period import Period
from ....iva.lookup import resolve_iva_rate
from ..authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..errors import FilingYearOutsideSupportEnvelopeError, RegistryValidationError
from ..eu_member_state_catalogue import require_eu_member_state
from ..facts.resolution import MappingFactQuery, ResolvedMappingFact, reading_dated_facts_below_support
from ..facts.variants import FactSelector
from ..iva_rate_kind_catalogue import require_iva_rate_kind
from ..schema_base import DateAxis
from ..schema_references import TemporalProjectionDirection
from ..snapshot_globals import SupportedFilingYearsCatalogue
from ..temporal import select_revision_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DECLARATION = Path(__file__).resolve().parents[4] / "_data" / "registry" / "aeat" / "legal"


@pytest.fixture
def operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as pinned:
        yield pinned


def _general_rate(operation: PinnedAuthorityOperation, on_date: date) -> ResolvedMappingFact:
    return resolve_iva_rate(
        require_eu_member_state("es", effective_date=on_date, authority=operation),
        require_iva_rate_kind("general", effective_date=on_date, authority=operation),
        on_date,
        operation=operation,
    )


def _pct(resolved: ResolvedMappingFact) -> str:
    return str({entry.key: entry.value for entry in resolved.payload.entries}["pct"])


def test_below_the_floor_a_fact_is_refused_outside_the_scope(operation: PinnedAuthorityOperation) -> None:
    before = operation.supported_filing_years().date_envelope().floor - timedelta(days=1)
    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        _general_rate(operation, before)


def test_below_the_floor_a_fact_inside_the_scope_is_marked_as_a_backward_projection(
    operation: PinnedAuthorityOperation,
) -> None:
    floor = operation.supported_filing_years().date_envelope().floor
    before = floor - timedelta(days=1)
    with reading_dated_facts_below_support():
        resolved = _general_rate(operation, before)
    assert resolved.projection_direction is TemporalProjectionDirection.BACKWARD
    assert resolved.projected_from_date == floor
    assert _pct(resolved) == "21"


def test_a_scope_answer_is_never_served_to_a_later_read_outside_it(operation: PinnedAuthorityOperation) -> None:
    before = operation.supported_filing_years().date_envelope().floor - timedelta(days=1)
    with reading_dated_facts_below_support():
        _general_rate(operation, before)
    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        _general_rate(operation, before)


def test_inside_the_support_the_scope_changes_no_answer(operation: PinnedAuthorityOperation) -> None:
    floor = operation.supported_filing_years().date_envelope().floor
    plain = _general_rate(operation, floor)
    with reading_dated_facts_below_support():
        scoped = _general_rate(operation, floor)
    assert scoped == plain
    assert plain.projection_direction is TemporalProjectionDirection.AUTHORED


def test_a_declared_legal_start_is_not_projected_across() -> None:
    """RDL 20/2012 art. 23 set the 21 % with effect from 2012-09-01; 18 % applied the day before."""

    def general_rate_query(on_date: date) -> MappingFactQuery:
        return MappingFactQuery(
            fact_id="iva-rate-schedule",
            date_axis=DateAxis.DEVENGO_DATE,
            effective_date=on_date,
            selectors=(
                FactSelector(name="member_state", value="es"),
                FactSelector(name="kind", value="general"),
                FactSelector(name="rate_role", value="ordinary"),
            ),
        )

    with bundled_indexed_authority().operation() as operation:
        legal_start = operation.legal_reference("real-decreto-ley-20-2012:art-23-dos").effective_from
    assert legal_start is not None
    with bundled_indexed_authority().operation() as operation, reading_dated_facts_below_support():
        resolved = operation.resolve_governed_fact(general_rate_query(legal_start))
        assert isinstance(resolved, ResolvedMappingFact)
        assert _pct(resolved) == "21"
        assert resolved.projection_direction is TemporalProjectionDirection.BACKWARD
        # The day before, the 18 % that Ley 26/2009 art. 79 set from 2010-07-01 still applied: the 21 % is not
        # stretched back across its legal start while the registry authors the rate it replaced.
        before_start = operation.resolve_governed_fact(general_rate_query(legal_start - timedelta(days=1)))
        assert isinstance(before_start, ResolvedMappingFact)
        assert _pct(before_start) == "18"


def test_a_filing_year_coordinate_stays_gated_inside_the_scope(operation: PinnedAuthorityOperation) -> None:
    floor = operation.supported_filing_years().floor
    with reading_dated_facts_below_support():
        with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
            operation.resolve_governed_fact(
                MappingFactQuery(
                    fact_id="deadlines.filing-window-clause",
                    date_axis=DateAxis.FILING_PERIOD,
                    effective_date=date(floor - 1, 3, 31),
                    filing_year=floor - 1,
                    period="1T",
                ),
            )
        with pytest.raises(FilingYearOutsideSupportEnvelopeError):
            select_revision_metadata(operation.modelo_directory("303"), filing_year=floor - 1, period="1T")


def test_the_floor_is_declared_relative_to_the_horizon_with_the_same_bounds(
    operation: PinnedAuthorityOperation,
) -> None:
    declared = tomllib.loads((_DECLARATION / "supported-filing-years.toml").read_text(encoding="utf-8"))
    table = declared["supported_filing_years"]
    assert "floor" not in table
    assert "hard_ceiling" not in table
    resolved = SupportedFilingYearsCatalogue.model_validate(table)
    assert resolved.floor == table["horizon"] - table["filing_grade_years_before_horizon"]
    assert resolved == operation.supported_filing_years()
    assert set(type(resolved).model_validate(resolved.model_dump()).model_dump()) == {
        "floor",
        "horizon",
        "hard_ceiling",
    }


@pytest.mark.parametrize(
    "table",
    (
        {"filing_grade_years_before_horizon": 1, "floor": 1, "horizon": 2},
        {"filing_grade_years_before_horizon": -1, "horizon": FOUR_DIGIT_YEAR_FIRST},
        {"filing_grade_years_before_horizon": True, "horizon": FOUR_DIGIT_YEAR_LAST},
        {"filing_grade_years_before_horizon": 1},
    ),
)
def test_a_malformed_relative_floor_is_refused(table: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SupportedFilingYearsCatalogue.model_validate(table)


@pytest.mark.parametrize("year", (FOUR_DIGIT_YEAR_FIRST, FOUR_DIGIT_YEAR_LAST))
def test_a_year_is_a_shape_at_both_ends(year: int) -> None:
    assert TypeAdapter(FilingYear).validate_python(year) == year
    assert Period.from_year_and_code(year, "0A").filing_year == year


@pytest.mark.parametrize("year", (FOUR_DIGIT_YEAR_FIRST - 1, FOUR_DIGIT_YEAR_LAST + 1))
def test_a_number_not_written_as_a_year_is_refused(year: int) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(FilingYear).validate_python(year)
