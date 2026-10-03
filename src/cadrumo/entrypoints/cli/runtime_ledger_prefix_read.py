"""Submit a ledger read addressed by transaction prefix and correlate its settled result."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from ...adapters.local_runtime.frontend_client import RuntimeFrontendClient
from ...core.operations import OperationEffect, profile_operation_subject
from .errors import CliRefusedBoundaryError
from .registered_operation_errors import invalid_completion_error
from .runtime_ledger_prefix import attach_submitted_ledger_prefix_verdict
from .runtime_registered_operation import run_registered_operation

_LEDGER_READ_TIMEOUT_SECONDS = 60


@runtime_checkable
class PrefixScopedProjection(Protocol):
    """A ledger projection that names the profile and prefix it answers for."""

    @property
    def profile_id(self) -> UUID:
        """Return the profile the projection was read from."""
        ...

    @property
    def transaction_prefix(self) -> str | None:
        """Return the normalised transaction prefix the read resolved."""
        ...


def read_ledger_prefix_projection[ResultT: BaseModel](
    client: RuntimeFrontendClient,
    request: BaseModel,
    *,
    prefix: str | None,
    definition_id: str,
    result_type: type[ResultT],
    extra_matches: Callable[[ResultT], bool] = lambda _result: True,
) -> ResultT:
    """Return the projection only when it answers the submitted profile, prefix and read-only receipt.

    A worker refusal for an unresolvable handle keeps the same no-recovery
    verdict as local prefix validation. A mismatch is refused as an invalid
    frame that retains the settled receipt's condition, effect and refusal code.
    """
    try:
        completed = run_registered_operation(
            client,
            request,
            definition_id=definition_id,
            subject_ref=profile_operation_subject(str(client.profile_id)),
            result_type=result_type,
            request_version=1,
            result_version=1,
            timeout=_LEDGER_READ_TIMEOUT_SECONDS,
        )
    except CliRefusedBoundaryError as error:
        attach_submitted_ledger_prefix_verdict(error)
        raise
    result = completed.projection
    if (
        not isinstance(result, PrefixScopedProjection)
        or result.profile_id != client.profile_id
        or result.transaction_prefix != prefix
        or not extra_matches(result)
        or completed.effect is not OperationEffect.NONE
    ):
        raise invalid_completion_error(completed)
    return result
