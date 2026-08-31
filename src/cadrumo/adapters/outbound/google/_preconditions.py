"""Canonical terminal-precondition transport for Google adapter refusals."""

from __future__ import annotations

from collections.abc import Mapping

from ....application.operator_actions._preconditions import no_action_precondition_verdict
from ....core.operator_action_enums import ActionEvidenceProvenance, NoRecoveryOutcome
from ..storage.errors import OutboundStorageError


def google_terminal_refusal(
    error: OutboundStorageError,
    *,
    condition_id: str,
    facts: Mapping[str, str | int | bool],
    provenance: ActionEvidenceProvenance,
    outcome: NoRecoveryOutcome,
) -> OutboundStorageError:
    """Clone ``error`` with one Google-owned terminal precondition verdict."""
    return type(error)(
        error.args[0] if error.args else None,
        context=error.context,
        translated_message=error.translated_message,
        precondition_verdict=no_action_precondition_verdict(
            condition_id=condition_id,
            facts=facts,
            provenance=provenance,
            outcome=outcome,
        ),
    )


__all__ = ["google_terminal_refusal"]
