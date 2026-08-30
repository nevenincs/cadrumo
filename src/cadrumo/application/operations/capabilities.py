"""Validated capability declarations for registered operation definitions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
)


class OperationReplayPolicy(StrEnum):
    """Idempotency and restart behavior declared by an operation definition."""

    NONE = "none"
    IDEMPOTENT_SUBMIT = "idempotent_submit"
    RESUMABLE = "resumable"


class OperationBaselinePolicy(StrEnum):
    """Binding required between an operation and domain-owned baseline state."""

    NONE = "none"
    REQUEST_BOUND = "request_bound"
    EXACT_APPROVAL = "exact_approval"


class OperationSensitiveInputPolicy(StrEnum):
    """Whether sensitive operands are absent or resolved through secure custody."""

    NONE = "none"
    SECURE_REFERENCE = "secure_reference"


class OperationRequestStoragePolicy(StrEnum):
    """Exclusive durable location for one operation's validated request."""

    SECURE_REFERENCE = "secure_reference"
    CREDENTIAL_FREE_JOURNAL = "credential_free_journal"


class OperationConflictScope(StrEnum):
    """Lease scope used to exclude conflicting operation owners."""

    NONE = "none"
    DEFINITION_SUBJECT = "definition_subject"


class OperationOwnedResource(StrEnum):
    """Supervisor-owned resource families requiring settled cleanup."""

    ASYNC_TASK = "async_task"
    PROCESS = "process"


class OperationCapabilities(BaseModel):
    """Complete, immutable capabilities of one registered operation type."""

    model_config = STRICT_FROZEN_CONFIG

    durability: OperationDurability
    cancellation: OperationCancellation
    deadline: OperationDeadline
    replay: OperationReplayPolicy
    baseline: OperationBaselinePolicy
    request_storage: OperationRequestStoragePolicy
    sensitive_input: OperationSensitiveInputPolicy
    conflict_scope: OperationConflictScope
    owned_resources: frozenset[OperationOwnedResource]
    permitted_effects: frozenset[OperationEffect]
    close_policy: OperationClosePolicy

    @model_validator(mode="after")
    def _validate_combinations(self) -> OperationCapabilities:
        self._validate_durability()
        self._validate_stopping()
        self._validate_close_policy()
        if (
            self.request_storage is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
            and self.sensitive_input is not OperationSensitiveInputPolicy.NONE
        ):
            raise ValueError("credential-free journal requests cannot declare sensitive request input")
        return self

    def _validate_durability(self) -> None:
        if not self.permitted_effects:
            raise ValueError("operation capabilities must declare at least one permitted effect")
        if self.durability is OperationDurability.EPHEMERAL:
            if self.permitted_effects != frozenset({OperationEffect.NONE}):
                raise ValueError("ephemeral operations may permit only the none effect")
            if self.replay is not OperationReplayPolicy.NONE:
                raise ValueError("ephemeral operations cannot promise durable replay")
            if self.conflict_scope is not OperationConflictScope.NONE:
                raise ValueError("ephemeral operations cannot declare a durable lease scope")
        else:
            if self.conflict_scope is OperationConflictScope.NONE:
                raise ValueError("recorded and resumable operations require a conflict scope")

        resumable = self.durability is OperationDurability.RESUMABLE
        if resumable != (self.replay is OperationReplayPolicy.RESUMABLE):
            raise ValueError("resumable durability and replay capability must be declared together")

    def _validate_stopping(self) -> None:
        if self.cancellation is OperationCancellation.CONTAINED and not self.owned_resources:
            raise ValueError("contained cancellation requires a supervisor-owned resource")
        if self.deadline is OperationDeadline.COOPERATIVE and self.cancellation is OperationCancellation.UNSUPPORTED:
            raise ValueError("cooperative deadlines require a cancellable executor")
        if self.deadline is OperationDeadline.ENFORCED:
            if self.cancellation is not OperationCancellation.CONTAINED:
                raise ValueError("enforced deadlines require contained cancellation")
            if not self.owned_resources:
                raise ValueError("enforced deadlines require a supervisor-owned resource")

    def _validate_close_policy(self) -> None:
        if (
            self.close_policy is OperationClosePolicy.REQUEST_CANCEL
            and self.cancellation is OperationCancellation.UNSUPPORTED
        ):
            raise ValueError("request-cancel close policy requires a cancellable executor")


__all__ = [
    "OperationBaselinePolicy",
    "OperationCapabilities",
    "OperationConflictScope",
    "OperationOwnedResource",
    "OperationReplayPolicy",
    "OperationRequestStoragePolicy",
    "OperationSensitiveInputPolicy",
]
