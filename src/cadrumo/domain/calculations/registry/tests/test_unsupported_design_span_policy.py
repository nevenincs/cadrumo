"""Unsafe design spans stay visible while remaining unavailable for filing."""

from __future__ import annotations

import pytest

from cadrumo.core import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry import (
    RegistryFailureCondition,
    RegistryValidationError,
    bundled_authority,
)

from .test_revision_span_matches_published_designs import _boundaries_for, _declared_revisions, _filing_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_KNOWN_UNSUPPORTED_SPANS = frozenset(
    {
        ("200", "2024-y-siguientes"),
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
        "modelo 200 revision 2024-y-siguientes declares 'calculation' authority grade, "
        "which cannot satisfy the requested 'filing' snapshot authority."
    )
    failure = error.registry_failure
    assert failure is not None
    assert failure.condition is RegistryFailureCondition.SNAPSHOT_AUTHORITY_GRADE_SUFFICIENT
    assert failure.facts == {
        "modelo": "200",
        "revision_id": "2024-y-siguientes",
        "requested_authority_grade": "filing",
        "declared_authority_grade": "calculation",
        "authority_grade_declared": True,
    }
