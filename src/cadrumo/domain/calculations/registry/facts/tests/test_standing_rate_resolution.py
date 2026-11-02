"""Nearest-edition selection for a fact declared a standing rate, through the real resolver."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ...errors import GovernedFactNotApplicableError, RegistryValidationError
from ...schema_base import DateAxis
from ...schema_references import TemporalProjectionDirection
from ...snapshot_globals import SupportedFilingYearsCatalogue
from ..resolution import ResolvedScalarFact, ScalarFactQuery, resolve_validated_governed_fact
from ..schema import GovernedFact
from ..variants import FactSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DIGEST = "a" * 64
_HORIZON = date.today().year
_FLOOR = _HORIZON - 4
_SUPPORT = SupportedFilingYearsCatalogue(floor=_FLOOR, horizon=_HORIZON)

# Two editions with a gap of an even number of days between their edges: the day
# halfway is equally far from both.
_FIRST_END = date(_FLOOR, 2, 1)
_SECOND_START = _FIRST_END + timedelta(days=20)
_MIDPOINT = _FIRST_END + timedelta(days=10)


def _variant(
    variant_id: str,
    value: str,
    *,
    valid_from: date,
    valid_to: date | None = None,
    selectors: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "variant_id": variant_id,
        "selectors": selectors,
        "date_axis": "filing_period",
        "valid_from": valid_from,
        "valid_to": valid_to,
        "payload": {"kind": "scalar", "value_type": "decimal", "value": value, "unit": "fraction"},
        "legal_refs": ("ley-37-1992:art-90",),
        "review_status": "agent_reviewed",
        "ownership": "authored",
    }


def _fact(*variants: dict[str, object], standing_rate: dict[str, object] | None = None) -> GovernedFact:
    return GovernedFact.model_validate(
        {"fact_id": "test.rate", "family": "scalar", "standing_rate": standing_rate, "variants": variants},
    )


_EDITIONS = (
    _variant("test.rate:first", "0.10", valid_from=date(_FLOOR, 1, 1), valid_to=_FIRST_END),
    _variant("test.rate:second", "0.20", valid_from=_SECOND_START, valid_to=date(_FLOOR + 1, 1, 1)),
)
_STANDING = _fact(*_EDITIONS, standing_rate={})


def _resolve(
    fact: GovernedFact,
    on_date: date,
    *,
    selectors: tuple[FactSelector, ...] = (),
    filing_year: int | None = None,
) -> ResolvedScalarFact:
    resolved = resolve_validated_governed_fact(
        fact,
        ScalarFactQuery(
            fact_id=fact.fact_id,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=on_date,
            selectors=selectors,
            filing_year=filing_year,
            period=None if filing_year is None else "0A",
        ),
        authority_digest=_DIGEST,
        support=_SUPPORT,
    )
    assert isinstance(resolved, ResolvedScalarFact)
    return resolved


def test_a_date_inside_an_edition_stays_published() -> None:
    resolved = _resolve(_STANDING, _FIRST_END)

    assert resolved.payload.value == Decimal("0.10")
    assert resolved.published_on_date
    assert resolved.projection_direction is TemporalProjectionDirection.AUTHORED
    assert resolved.projected_from_date is None


def test_a_gap_reads_the_closer_edition_on_each_side_of_the_midpoint() -> None:
    earlier = _resolve(_STANDING, _MIDPOINT - timedelta(days=1))
    later = _resolve(_STANDING, _MIDPOINT + timedelta(days=1))

    assert earlier.payload.value == Decimal("0.10")
    assert earlier.projection_direction is TemporalProjectionDirection.FORWARD
    assert earlier.projected_from_date == _FIRST_END
    assert not earlier.published_on_date

    assert later.payload.value == Decimal("0.20")
    assert later.projection_direction is TemporalProjectionDirection.BACKWARD
    assert later.projected_from_date == _SECOND_START
    assert not later.published_on_date


def test_equal_distance_takes_the_earlier_edition() -> None:
    resolved = _resolve(_STANDING, _MIDPOINT)

    assert resolved.payload.value == Decimal("0.10")
    assert resolved.projected_from_date == _FIRST_END


def test_a_date_past_the_last_edition_carries_it_forward() -> None:
    last_end = date(_FLOOR + 1, 1, 1)
    resolved = _resolve(_STANDING, last_end + timedelta(days=400))

    assert resolved.payload.value == Decimal("0.20")
    assert resolved.projection_direction is TemporalProjectionDirection.FORWARD
    assert resolved.projected_from_date == last_end


def test_a_date_below_the_floor_and_every_edition_reads_the_first_without_any_scope() -> None:
    resolved = _resolve(_STANDING, date(_FLOOR - 30, 6, 15))

    assert resolved.payload.value == Decimal("0.10")
    assert resolved.projection_direction is TemporalProjectionDirection.BACKWARD
    assert resolved.projected_from_date == date(_FLOOR, 1, 1)
    assert not resolved.published_on_date


def test_projection_keeps_the_edition_review_status_and_evidence() -> None:
    """A projected read cites what the edition cites and claims no more review than it has."""
    published = _resolve(_STANDING, _FIRST_END)
    projected = _resolve(_STANDING, _FIRST_END + timedelta(days=1))

    assert projected.review_status == published.review_status
    assert projected.ownership == published.ownership
    assert projected.legal_refs == published.legal_refs
    assert projected.source_variant_id == published.source_variant_id


def test_a_fact_without_the_declaration_keeps_its_gap() -> None:
    fact = _fact(*_EDITIONS)

    with pytest.raises(GovernedFactNotApplicableError):
        _resolve(fact, _MIDPOINT)


def test_a_fact_without_the_declaration_keeps_its_floor() -> None:
    fact = _fact(*_EDITIONS)

    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        _resolve(fact, date(_FLOOR - 1, 6, 15))


def test_a_filing_year_coordinate_stays_gated_for_a_standing_rate() -> None:
    fact = _fact(
        {
            **_variant("test.rate:periodic", "0.10", valid_from=date(_FLOOR, 1, 1)),
            "period_selector": {"periods": ("0A",), "year_from": _FLOOR},
        },
        standing_rate={},
    )

    with pytest.raises(RegistryValidationError, match="outside the supported filing years"):
        _resolve(fact, date(_FLOOR - 1, 12, 31), filing_year=_FLOOR - 1)


def test_the_selector_narrows_the_claim_to_the_tracks_carrying_it() -> None:
    ordinary = {"name": "role", "value": "ordinary"}
    temporary = {"name": "role", "value": "temporary"}
    fact = _fact(
        _variant(
            "test.rate:ordinary", "0.21", valid_from=date(_FLOOR, 1, 1), valid_to=_FIRST_END, selectors=(ordinary,)
        ),
        _variant(
            "test.rate:temporary", "0.05", valid_from=date(_FLOOR, 1, 1), valid_to=_FIRST_END, selectors=(temporary,)
        ),
        standing_rate={"track_selector": ordinary},
    )
    after = _FIRST_END + timedelta(days=1)

    assert _resolve(fact, after, selectors=(FactSelector(**ordinary),)).payload.value == Decimal("0.21")
    with pytest.raises(GovernedFactNotApplicableError):
        _resolve(fact, after, selectors=(FactSelector(**temporary),))


def test_an_absent_track_is_not_answered_by_another() -> None:
    ordinary = {"name": "role", "value": "ordinary"}
    fact = _fact(
        _variant("test.rate:ordinary", "0.21", valid_from=date(_FLOOR, 1, 1), selectors=(ordinary,)),
        standing_rate={"track_selector": ordinary},
    )

    with pytest.raises(GovernedFactNotApplicableError):
        _resolve(
            fact, _FIRST_END, selectors=(FactSelector(name="role", value="ordinary"), FactSelector(name="x", value="y"))
        )


def test_a_selector_no_variant_carries_is_refused_at_validation() -> None:
    with pytest.raises((RegistryValidationError, ValidationError), match="no variant carries"):
        _fact(*_EDITIONS, standing_rate={"track_selector": {"name": "role", "value": "ordinary"}})


def test_the_declaration_is_absent_from_a_serialized_fact_that_makes_none() -> None:
    """An undeclared fact's published component bytes do not change."""
    assert "standing_rate" not in _fact(*_EDITIONS).model_dump()
    assert "standing_rate" in _STANDING.model_dump()
