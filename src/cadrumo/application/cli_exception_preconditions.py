"""Application-owned outcomes for CLI exception boundaries.

Exception boundaries observe a transport failure but must not manufacture a
copy-paste command from an error string.  This module gives those boundaries a
small closed policy vocabulary: each condition records its observed fact and
explicitly states that no executable recovery can be bound from that fact.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from ..core import (
    ActionConditionality,
    ActionEvidenceProvenance,
    NoRecoveryOutcome,
)
from .operator_actions import (
    ConditionEvidence,
    PreconditionVerdict,
)


class CliExceptionPrecondition(StrEnum):
    """Closed failed-condition identities for the CLI exception slice."""

    VALIDATION_BOUNDARY = "cli.validation.boundary_clean"
    UNEXPECTED_BOUNDARY = "cli.runtime.unexpected_absent"
    STORED_DATA_VALID = "cli.storage.persisted_data_valid"
    COMMAND_GROUP_AVAILABLE = "cli.command_group.available"
    REFUSAL_RETRIED = "cli.refusal.completed"
    CONFIG_BOUNDARY = "cli.config.boundary_clean"
    STDIN_INTERACTIVE = "cli.stdin.interactive"
    LOGIN_COMPLETED = "cli.profile.login.completed"
    OVERVIEW_PROFILE_COMPLETE = "cli.overview.profile.complete"
    PROFILE_EXPORT_REQUEST_COMPLETE = "cli.profile.export_request.complete"
    PROFILE_IMPORT_PATH_SUPPLIED = "cli.profile.import_path.supplied"
    GOOGLE_CONFIGURATION_COMPLETE = "cli.google.configuration.complete"
    GOOGLE_MIRROR_REQUEST_COMPLETE = "cli.google.mirror_request.complete"


def cli_exception_no_recovery_verdict(
    condition: CliExceptionPrecondition,
    *,
    facts: Mapping[str, str | int | bool],
    outcome: NoRecoveryOutcome = NoRecoveryOutcome.OPERATOR_DECISION,
) -> PreconditionVerdict:
    """Return one explicit non-actionable outcome for an exception boundary.

    The facts name what was observed, while the closed outcome prevents a CLI
    adapter from smuggling an unbound command template into a recovery field.
    """
    condition_id = condition.value
    return PreconditionVerdict(
        failed_condition_id=condition_id,
        evidence=(
            ConditionEvidence(
                condition_id=condition_id,
                evidence_id=f"{condition_id}.observation",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                values=facts,
            ),
        ),
        conditionality=ActionConditionality.NOT_APPLICABLE,
        no_recovery_outcome=outcome,
    )


__all__ = ["CliExceptionPrecondition", "cli_exception_no_recovery_verdict"]
