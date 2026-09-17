"""Review comparison is independent of a revision's physical storage edge."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from .....core.revision_review import RevisionReviewStatus
from ..errors import RegistryValidationError
from ..schema import ModeloRevision
from ..schema_references import PeriodSelector

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PREDECESSOR = "2024"


def _revision(
    *,
    predecessor: str | None,
    review_status: RevisionReviewStatus,
    reviewed_against: str | None,
) -> ModeloRevision:
    reviewed = review_status is not RevisionReviewStatus.PENDING_REVIEW
    return ModeloRevision(
        id="2025",
        localization_key="scope",
        valid_from=date(2025, 1, 1),
        period_selector=PeriodSelector(year_from=2025, periods=("0A",)),
        legal_refs=("ley-58-2003:art-29",),
        source_refs=("aeat-manual",),
        predecessor=predecessor,
        review_status=review_status,
        reviewed_by="agent:scope" if reviewed else None,
        reviewed_at=date(2026, 9, 10) if reviewed else None,
        reviewed_against=reviewed_against,
    )


def test_a_reviewed_delta_edition_naming_its_predecessor_is_accepted() -> None:
    revision = _revision(
        predecessor=_PREDECESSOR, review_status=RevisionReviewStatus.AGENT_REVIEWED, reviewed_against=_PREDECESSOR
    )
    assert revision.reviewed_against == _PREDECESSOR


def test_an_unreviewed_delta_edition_needs_no_scope() -> None:
    revision = _revision(
        predecessor=_PREDECESSOR, review_status=RevisionReviewStatus.PENDING_REVIEW, reviewed_against=None
    )
    assert revision.reviewed_against is None


@pytest.mark.parametrize("status", [RevisionReviewStatus.AGENT_REVIEWED, RevisionReviewStatus.OPERATOR_REVIEWED])
def test_a_reviewed_delta_without_a_comparison_retains_full_edition_scope(status: RevisionReviewStatus) -> None:
    revision = _revision(predecessor=_PREDECESSOR, review_status=status, reviewed_against=None)
    assert revision.reviewed_against is None


def test_a_comparison_may_name_a_revision_other_than_the_storage_predecessor() -> None:
    revision = _revision(
        predecessor=_PREDECESSOR,
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewed_against="2023",
    )
    assert revision.reviewed_against == "2023"


def test_a_scope_on_an_unreviewed_delta_edition_is_refused() -> None:
    with pytest.raises(ValidationError, match="a review scope belongs to a review") as refusal:
        _revision(
            predecessor=_PREDECESSOR, review_status=RevisionReviewStatus.PENDING_REVIEW, reviewed_against=_PREDECESSOR
        )
    assert isinstance(refusal.value.errors()[0]["ctx"]["error"].__cause__, RegistryValidationError)


def test_a_comparison_reference_does_not_require_a_storage_predecessor() -> None:
    revision = _revision(
        predecessor=None,
        review_status=RevisionReviewStatus.AGENT_REVIEWED,
        reviewed_against=_PREDECESSOR,
    )
    assert revision.reviewed_against == _PREDECESSOR
