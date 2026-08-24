"""Unsafe design spans stay visible while remaining unavailable for filing."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry._authority import bundled_authority
from cadrumo.domain.calculations.registry._errors import RegistryValidationError
from cadrumo.domain.calculations.registry._schema import RegistryAuthorityGrade

from .test_revision_span_matches_published_designs import _boundaries_for, _declared_revisions, _filing_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_KNOWN_UNSUPPORTED_SPANS = frozenset(
    {
        ("200", "2024-y-siguientes"),
        ("763", "2011-y-siguientes"),
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
    with pytest.raises(RegistryValidationError, match="Validate and attest the revision at the requested grade"):
        bundled_authority().snapshot(
            "200",
            filing_year=2025,
            period="0A",
            grade=RegistryAuthorityGrade.FILING,
        )
