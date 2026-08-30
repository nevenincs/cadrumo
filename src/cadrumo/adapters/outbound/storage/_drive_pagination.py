"""Shared containment for Google Drive ``nextPageToken`` pagination."""

from __future__ import annotations

from ....application.operator_actions import no_action_precondition_verdict
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from .errors import OutboundStorageNetworkError


def next_drive_page_token(value: object, *, seen_tokens: set[str], action: str) -> str | None:
    """Validate the next Drive page token and refuse pagination cycles."""
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise OutboundStorageNetworkError(
            "Drive returned a non-string nextPageToken",
            context={"action": action, "token_type": type(value).__name__},
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.drive.pagination.token_string",
                facts={"operation": action, "token_type": type(value).__name__},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    if value in seen_tokens:
        raise OutboundStorageNetworkError(
            "Drive returned a repeated nextPageToken",
            context={"action": action, "page_token": value},
            precondition_verdict=no_action_precondition_verdict(
                condition_id="storage.drive.pagination.token_unique",
                facts={"operation": action, "token_repeated": True},
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    seen_tokens.add(value)
    return value
