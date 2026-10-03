"""Validated capability declarations for registered operation definitions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
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
    @pydantic_validation_boundary
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


# Named capability profiles shared by several registered operations. Every
# profile here is recorded, leases the definition subject, owns no supervisor
# resource and lets its frontend detach; its name spells out the remaining
# axes, so an operation that names a profile still declares its whole policy:
#
# - IDEMPOTENT / NON_IDEMPOTENT: idempotent-submit replay, or none.
# - REQUEST_BOUND: baseline bound to the request; absent means no baseline.
# - COOPERATIVE: cooperative cancellation and deadline; absent means the
#   executor is not cancellable and has no deadline.
# - JOURNALED: credential-free journal request with no sensitive input.
#   SECURE_INPUT: secure-reference request carrying sensitive input.
#   SECURE_STORED: secure-reference request without sensitive input.
# - READ: may only leave no effect (or unknown after owner loss).
#   UPDATE: may also fully apply, never partially.
#   PARTIAL_UPDATE: may also leave a partially applied effect.
#   REQUIRED_UPDATE: must fully apply (or be unknown after owner loss);
#   finishing with no effect is not an admissible outcome.
#
# A declaration that differs on any axis stays inline at its definition.

_READ_EFFECTS = frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN})
_REQUIRED_UPDATE_EFFECTS = frozenset({OperationEffect.UPDATED, OperationEffect.UNKNOWN})
_PARTIAL_UPDATE_EFFECTS = frozenset(
    {OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.PARTIAL, OperationEffect.UNKNOWN}
)

RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_READ_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_READ_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_READ_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_REQUIRED_UPDATE_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_PARTIAL_UPDATE_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.REQUEST_BOUND,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_READ_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.UNSUPPORTED,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.REQUEST_BOUND,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=_PARTIAL_UPDATE_EFFECTS,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)
RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.COOPERATIVE,
    deadline=OperationDeadline.COOPERATIVE,
    replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
    baseline=OperationBaselinePolicy.REQUEST_BOUND,
    request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
    sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset(),
    permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
    close_policy=OperationClosePolicy.DETACH_ALLOWED,
)


__all__ = [
    "RECORDED_COOPERATIVE_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_UPDATE_CAPABILITIES",
    "RECORDED_IDEMPOTENT_JOURNALED_READ_CAPABILITIES",
    "RECORDED_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES",
    "RECORDED_IDEMPOTENT_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES",
    "RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES",
    "RECORDED_IDEMPOTENT_SECURE_INPUT_REQUIRED_UPDATE_CAPABILITIES",
    "RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES",
    "RECORDED_IDEMPOTENT_SECURE_STORED_READ_CAPABILITIES",
    "RECORDED_IDEMPOTENT_SECURE_STORED_UPDATE_CAPABILITIES",
    "RECORDED_NON_IDEMPOTENT_JOURNALED_UPDATE_CAPABILITIES",
    "RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_PARTIAL_UPDATE_CAPABILITIES",
    "RECORDED_NON_IDEMPOTENT_REQUEST_BOUND_SECURE_INPUT_READ_CAPABILITIES",
    "RECORDED_NON_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES",
    "OperationBaselinePolicy",
    "OperationCapabilities",
    "OperationConflictScope",
    "OperationOwnedResource",
    "OperationReplayPolicy",
    "OperationRequestStoragePolicy",
    "OperationSensitiveInputPolicy",
]
