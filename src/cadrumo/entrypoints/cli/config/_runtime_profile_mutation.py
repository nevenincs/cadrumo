"""CLI boundary for one settled runtime profile mutation and its revision witness."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ....adapters.local_runtime.frontend_client import RuntimeFrontendRefusedError
from ....adapters.local_runtime.profile_mutations import (
    ProfileMutationCompletion,
    ProfileMutationRequest,
    ProfileMutationRunError,
    run_profile_mutation,
)
from ....application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ....application.runtime.deadline_budget import remaining_budget
from ....application.user_profile.view_operation import ProfileViewPageKind
from ....domain.user_profile.values import ProfileSetupState
from ..errors import CliRefusedBoundaryError

if TYPE_CHECKING:
    from ....adapters.local_runtime.frontend_client import ProfileViewCollection, RuntimeFrontendClient


_MUTATION_TIMEOUT_SECONDS = 120.0


def mutation_deadline() -> float:
    """Give baseline, canonical mutation and readback one total deadline."""
    return time.monotonic() + _MUTATION_TIMEOUT_SECONDS


def read_mutation_baseline(
    client: RuntimeFrontendClient, *, deadline: float, page_kind: ProfileViewPageKind = ProfileViewPageKind.FACTS
) -> ProfileViewCollection:
    """Capture a complete current-format view with its canonical CAS pair."""
    try:
        return client.read_profile_view((page_kind,), timeout=remaining_budget(deadline))
    except RuntimeFrontendRefusedError as error:
        raise CliRefusedBoundaryError(error.reason, context={"reason": error.reason}) from error


def execute_profile_mutation(
    client: RuntimeFrontendClient,
    request: ProfileMutationRequest,
    *,
    deadline: float,
    expected_setup_state: ProfileSetupState | None = None,
) -> tuple[ProfileMutationCompletion, ProfileViewCollection]:
    """Require an exact post-settlement revision before disclosing its digest."""
    try:
        completed = run_profile_mutation(client, request, timeout=remaining_budget(deadline))
    except ProfileMutationRunError as error:
        context = {
            "reason": error.reason,
            "operation_id": str(error.operation_id),
            "effect": error.effect.value if error.effect else "unknown",
        }
        if error.terminal_condition is not None:
            context["terminal_condition"] = error.terminal_condition.value
        raise CliRefusedBoundaryError(error.reason, context=context) from error

    try:
        current = client.read_profile_view((ProfileViewPageKind.FACTS,), timeout=remaining_budget(deadline))
        if current.record_revision != completed.projection.record_revision or (
            expected_setup_state is not None and current.setup_state is not expected_setup_state
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    except (RuntimeRefusalError, RuntimeFrontendRefusedError) as error:
        # The operation has already settled successfully. A later view failure
        # cannot be presented as a rollback or an unsubmitted command.
        raise CliRefusedBoundaryError(
            translated_message="cli.config.profile.mutation.committed_view_unavailable",
            context={
                "operation_id": str(completed.operation_id),
                "commit_state": "succeeded",
                "record_revision": completed.projection.record_revision,
                "read_state": "unavailable",
            },
        ) from error
    return completed, current


__all__ = ["execute_profile_mutation", "mutation_deadline", "read_mutation_baseline"]
