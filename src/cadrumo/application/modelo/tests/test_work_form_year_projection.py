"""The form serves whether its filing year is carried across from another edition.

The expected direction of each year comes from the authored editions the
published registry holds, not from the resolver under test: a year an edition
authors is not projected, a year after the newest edition projects forward and a
year before the oldest edition projects backward. The support envelope
reaches no year below Modelo 100's oldest edition, so the backward direction has
no population to exercise here.
"""

from __future__ import annotations

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema_references import TemporalProjectionDirection
from ....domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    projected_exercise,
    supported_authored_exercises,
)
from .work_form_fixture import built_form

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_MODELO = "100"
_ANNUAL = "0A"


def test_an_authored_year_is_served_as_not_projected(operation: PinnedAuthorityOperation) -> None:
    years = supported_authored_exercises(_MODELO)
    assert years, "the registry authors no supported year, so this proves nothing"
    for year in years:
        projection = built_form(operation, _MODELO, year, _ANNUAL).year_projection
        assert projection.direction is TemporalProjectionDirection.AUTHORED, year
        assert projection.authored_filing_year == year
        assert projection.words is None, year


def test_a_year_after_the_newest_edition_is_served_as_projected_forward(operation: PinnedAuthorityOperation) -> None:
    year = projected_exercise(_MODELO)
    newest = authored_revisions(_MODELO)[-1]
    projection = built_form(operation, _MODELO, year, _ANNUAL).year_projection
    assert projection.direction is TemporalProjectionDirection.FORWARD
    assert projection.authored_filing_year < year
    assert newest.valid_to is not None
    assert projection.authored_filing_year == newest.valid_to.year
    assert projection.reachable_grade is not RegistryAuthorityGrade.FILING


def test_a_projected_year_says_in_its_header_that_it_cannot_be_filed(operation: PinnedAuthorityOperation) -> None:
    year = projected_exercise(_MODELO)
    projection = built_form(operation, _MODELO, year, _ANNUAL).year_projection

    assert projection.words == tr(
        "application.modelo.findings.registry_filing_year_projected",
        modelo=_MODELO,
        filing_year=year,
        period=_ANNUAL,
        authored_filing_year=projection.authored_filing_year,
        locale="en",
    )
