"""Unsafe design spans stay visible while remaining unavailable for filing."""

from __future__ import annotations

import pytest

from .....core import RegistryAuthorityGrade
from ..authority import bundled_authority
from ..errors import RegistryFailureCondition, RegistryValidationError
from .test_revision_span_matches_published_designs import _boundaries_for, _declared_revisions, _filing_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Spans that declare design boundaries while their own authority_grade keeps
#: them off the filing path: modelos 126 and 128 at 'calculation', both modelo
#: 308 eras at 'applicability'.
#:
#: Modelo 200's 2024 revision belongs here on grade -- it declares 'calculation'
#: too -- and is absent only because a span needs boundaries to be counted, and
#: that revision currently has no export fragments at all while its tree awaits
#: regeneration. It returns to this set with them, and it is listed here in
#: prose so its reappearance reads as the tree coming back rather than as a new
#: regression.
_KNOWN_UNSUPPORTED_SPANS = frozenset(
    {
        ("126", "2019-y-siguientes"),
        ("128", "2019-y-siguientes"),
        ("308", "2009-2011-junio"),
        ("308", "2011-julio-2015"),
    },
)


def _unsupported_spans() -> set[tuple[str, str]]:
    filing = {(modelo.id, revision_id) for modelo, revision_id, _revision in _filing_revisions()}
    return {
        (modelo.id, revision_id)
        for modelo, revision_id, revision in _declared_revisions()
        if (modelo.id, revision_id) not in filing and _boundaries_for(modelo.id, revision)
    }


def test_known_unsupported_spans_remain_detectable_and_pinned() -> None:
    """A grade correction may remove support, never erase the evidence backlog."""
    assert _unsupported_spans() == _KNOWN_UNSUPPORTED_SPANS


def test_modelo_200_filing_request_refuses_at_the_authority_boundary() -> None:
    """The unsafe mixed-layout revision must fail before any filing bytes exist."""
    with pytest.raises(RegistryValidationError) as exc_info:
        bundled_authority().snapshot(
            "200",
            filing_year=2025,
            period="0A",
            grade=RegistryAuthorityGrade.FILING,
        )

    error = exc_info.value
    assert str(error) == (
        "modelo 200 revision 2025-y-siguientes declares 'calculation' authority grade, "
        "which cannot satisfy the requested 'filing' snapshot authority."
    )
    failure = error.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
    assert failure.facts == {
        "modelo": "200",
        "revision_id": "2025-y-siguientes",
        "requested_authority_grade": "filing",
        "declared_authority_grade": "calculation",
        "authority_grade_declared": True,
    }
