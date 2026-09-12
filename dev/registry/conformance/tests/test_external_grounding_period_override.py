"""Oracle attribution reads the period surface of the year the payload was captured for.

A captured payload carries a filing year and a period. Matching that period
against the flat tuple attributes it to a revision that does not file the
period in that year, which is exactly what an override declares.
"""

from __future__ import annotations

from typing import Final

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.schema_references import PeriodOverride, PeriodSelector

from ..external_grounding import _select_revision_for_filing_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_MODELO: Final = "130"
_REVISION: Final = "2019-y-siguientes"
_YEAR: Final = 2024
_DROPPED: Final = "1T"
_SERVED: Final = ("2T", "3T", "4T")


def _overridden_revision() -> ModeloRevision:
    """The bundled revision with :data:`_YEAR` overridden to drop :data:`_DROPPED`."""
    revision = bundled_authority().modelo(_MODELO).revisions[_REVISION]
    declared = revision.period_selector
    assert declared.periods[0] == _DROPPED, "the fixture must discriminate a flat read"
    selector = PeriodSelector(
        years=declared.years,
        year_from=declared.year_from,
        year_to=declared.year_to,
        periods=declared.periods,
        period_overrides=(PeriodOverride(year=_YEAR, periods=_SERVED),),
    )
    return revision.model_copy(update={"period_selector": selector})


def test_a_period_the_override_year_drops_is_not_attributed() -> None:
    revisions = (_overridden_revision(),)

    assert _select_revision_for_filing_year(revisions, filing_year=_YEAR, period=_DROPPED) is None


def test_a_period_the_override_year_serves_is_attributed() -> None:
    revisions = (_overridden_revision(),)

    selected = _select_revision_for_filing_year(revisions, filing_year=_YEAR, period=_SERVED[0])

    assert selected is not None
    assert selected.id == _REVISION


def test_a_year_outside_the_override_keeps_the_flat_surface() -> None:
    revisions = (_overridden_revision(),)

    selected = _select_revision_for_filing_year(revisions, filing_year=_YEAR + 1, period=_DROPPED)

    assert selected is not None
    assert selected.id == _REVISION
