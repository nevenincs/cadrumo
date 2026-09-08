"""Shared-gate adapter for persisted filing-draft registry coordinates."""

from __future__ import annotations

from ...domain.filing.errors import ModeloDraftError
from ...domain.filing.schema import ModeloDraft
from ..calculations.revision_carry_gate import revision_carry_outcome


def require_modelo_draft_coordinates_current(draft: ModeloDraft) -> ModeloDraft:
    """Return a persisted draft only when its producing registry coordinate is current."""
    outcome = revision_carry_outcome(draft.snapshot_ref)
    if outcome.refused:
        raise ModeloDraftError(
            translated_message="application.filing.review.errors.registry_review_mismatch",
            context={
                "modelo": draft.modelo,
                "filing_year": str(draft.period.filing_year),
                "period": draft.period.registry_token,
                "stored_revision": str(draft.snapshot_ref.revision_id),
                "law_revision": str(outcome.selected_revision_id or "unresolvable"),
            },
        )
    return draft


__all__ = ["require_modelo_draft_coordinates_current"]
