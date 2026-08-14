"""Closed review provenance for shipped legal-catalogue references."""

from __future__ import annotations

from enum import StrEnum


class LegalReviewStatus(StrEnum):
    """Assurance attained by review of one legal reference."""

    PENDING_REVIEW = "pending_review"
    AGENT_REVIEWED = "agent_reviewed"
    OPERATOR_REVIEWED = "operator_reviewed"


REVIEWED_LEGAL_STATUSES: frozenset[LegalReviewStatus] = frozenset(
    status for status in LegalReviewStatus if status is not LegalReviewStatus.PENDING_REVIEW
)


__all__ = ["REVIEWED_LEGAL_STATUSES", "LegalReviewStatus"]
