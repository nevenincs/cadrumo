"""Ports for resolving application preconditions at an outer surface.

Application code owns the factual verdict.  An outer composition root owns the
catalogue and live command tree that can turn an optional action reference into
a transport target.  The projection below is the only inward-owned join; it
does not import a CLI, harness, or other entrypoint package.
"""

from __future__ import annotations

from typing import Protocol

from ...core.json_contract import (
    ActionConditionEvidence,
    ResolvedActionArgument,
    ResolvedActionReference,
    ResolvedPreconditionAction,
)
from .models import PreconditionVerdict


class PreconditionActionResolutionPort(Protocol):
    """Resolve one application action against an outer live surface."""

    def resolve_action_reference(self, verdict: PreconditionVerdict) -> ResolvedActionReference | None: ...


def project_precondition_action(
    verdict: PreconditionVerdict,
    *,
    resolver: PreconditionActionResolutionPort,
) -> ResolvedPreconditionAction:
    """Project a factual application verdict through an injected outer resolver.

    The resolver is intentionally passed as a port rather than imported here:
    only the outer composition root knows how a catalogue action maps to a live
    command path.  Evidence and argument provenance remain application-owned
    and are copied without presentation or command-string reconstruction.
    """
    action = resolver.resolve_action_reference(verdict)
    if (verdict.action is None) != (action is None):
        raise ValueError("precondition action resolver disagrees with verdict action presence")

    return ResolvedPreconditionAction(
        failed_condition_id=verdict.failed_condition_id,
        evidence=tuple(
            ActionConditionEvidence(
                condition_id=item.condition_id,
                evidence_id=item.evidence_id,
                provenance=item.provenance,
                values=item.values,
            )
            for item in verdict.evidence
        ),
        action=action,
        argument_bindings=tuple(
            ResolvedActionArgument(
                argument_name=item.argument_name,
                status=item.status,
                value=item.value,
                source=item.source,
                source_key=item.source_key,
                source_evidence_id=item.source_evidence_id,
            )
            for item in verdict.argument_bindings
        ),
        missing_argument_names=verdict.missing_argument_names,
        conditionality=verdict.conditionality,
        no_recovery_outcome=verdict.no_recovery_outcome,
    )


__all__ = ["PreconditionActionResolutionPort", "project_precondition_action"]
