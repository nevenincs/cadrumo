"""Administrative registry tokens have no filing period; malformed tokens still refuse."""

from __future__ import annotations

import pytest

from .....core.period import Period, PeriodError
from ..authority import bundled_indexed_authority
from ..errors import NoRevisionForPeriodError
from ..schema_base import filing_period_from_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize("token", ("comunicacion", "variacion", "ALTA", "baja"))
def test_administrative_registry_token_has_no_filing_period(token: str) -> None:
    assert filing_period_from_scope(2026, token) is None


def test_filing_period_token_builds_its_period() -> None:
    assert filing_period_from_scope(2026, "4T") == Period.from_year_and_code(2026, "4T")


@pytest.mark.parametrize(
    ("filing_year", "token"),
    (
        pytest.param(2026, "garbage", id="unknown-token"),
        pytest.param(2026, "EVENT-N", id="symbolic-event-selector"),
        pytest.param(1970, "4T", id="year-outside-period-range"),
    ),
)
def test_malformed_token_or_year_is_not_silenced(filing_year: int, token: str) -> None:
    with pytest.raises(PeriodError):
        filing_period_from_scope(filing_year, token)


def test_declared_administrative_token_builds_a_snapshot_without_filing_period() -> None:
    with bundled_indexed_authority().operation() as operation:
        snapshot = operation.snapshot("145", filing_year=2026, period="comunicacion")

    assert snapshot.filing_period is None
    assert snapshot.period == "comunicacion"
    assert snapshot.revision.id == "2012-01-31-y-siguientes"


def test_undeclared_administrative_token_is_refused_at_revision_selection() -> None:
    with (
        bundled_indexed_authority().operation() as operation,
        pytest.raises(NoRevisionForPeriodError, match="period='alta'"),
    ):
        operation.snapshot("145", filing_year=2026, period="alta")
