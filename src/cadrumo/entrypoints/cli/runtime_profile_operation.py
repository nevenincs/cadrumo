"""Submit exact-profile registered operations and correlate their settled results."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from .registered_operation_contracts import RegisteredOperationCompletion
from .registered_operation_errors import invalid_completion_error
from .runtime_registered_operation import run_registered_operation

_DEFAULT_TIMEOUT_SECONDS = 120


@runtime_checkable
class ProfileScopedProjection(Protocol):
    """A projection that names the profile bucket it was read from."""

    @property
    def bucket_id(self) -> str:
        """Return the profile bucket identifier."""
        ...


def submit_profile_operation[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    profile_id: UUID,
    request: BaseModel,
    *,
    result_type: type[ResultT],
    definition_id: str,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> RegisteredOperationCompletion[ResultT]:
    """Submit one version-1 registered operation over the client bound to the active profile."""
    return run_registered_operation(
        client,
        request,
        definition_id=definition_id,
        subject_ref=profile_operation_subject(str(profile_id)),
        result_type=result_type,
        request_version=1,
        result_version=1,
        timeout=timeout,
    )


def settled_projection[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
    result_type: type[ResultT],
    correlate: Callable[[ResultT], None],
    *,
    effect: OperationEffect = OperationEffect.NONE,
) -> ResultT:
    """Return the projection only when it matches its request and settled receipt.

    ``correlate`` raises when the projection disagrees with what the command
    submitted. Any disagreement is refused as an invalid frame that still names
    the operation and keeps its observed effect, so a committed effect is never
    hidden behind a client-side validation failure.
    """
    try:
        projection = completed.projection
        if not isinstance(projection, result_type):
            raise ValueError("result projection has an invalid type")
        correlate(projection)
        if (
            completed.terminal_condition is not OperationTerminalCondition.SUCCEEDED
            or completed.refusal_code is not None
            or completed.effect is not effect
        ):
            raise ValueError("result disagrees with its settled receipt")
    except Exception:
        raise invalid_completion_error(completed) from None
    return projection


def settled_profile_projection[ResultT: BaseModel](
    completed: RegisteredOperationCompletion[ResultT],
    result_type: type[ResultT],
    profile_id: UUID,
    correlate: Callable[[ResultT], None],
) -> ResultT:
    """Return a read-only projection that names the submitted profile bucket and matches the request."""

    def correlate_profile(projection: ResultT) -> None:
        if not isinstance(projection, ProfileScopedProjection) or projection.bucket_id != str(profile_id):
            raise ValueError("read result does not match its submitted profile")
        correlate(projection)

    return settled_projection(completed, result_type, correlate_profile)
