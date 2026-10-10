"""The actor label an executing operation records for what it writes.

An operation stores who acted in its reports and events. Nothing authenticates
a label a request carries, so the label of an agent's execution is taken from
the session that admitted it, and a person's execution keeps the label the
person's frontend supplied.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from ..user_profile.access_contracts import SessionKind
from .models import OperationIdentity
from .registry import OperationFrontendProjection

if TYPE_CHECKING:
    from .owner import OperationExecutorContext


@dataclass(frozen=True, slots=True)
class OperationExecutionCaller:
    """The frontend and session one executing invocation was admitted through."""

    frontend: OperationFrontendProjection
    session_kind: SessionKind
    client_id: UUID
    """The session's client: an identifier, never a credential."""


type OperationExecutionCallerReader = Callable[[OperationIdentity], OperationExecutionCaller]
"""The session host's answer for one invocation; it refuses an invocation it did not admit."""


def execution_actor_label(
    reader: OperationExecutionCallerReader | None, context: OperationExecutorContext, *, supplied: str
) -> str:
    """Return the label to record as the actor of the execution ``context`` belongs to.

    An execution admitted on the MCP frontend is an agent's. Its label names
    the session's kind and client, and the label the request supplied is not
    recorded. Every other frontend records the supplied label unchanged.

    ``reader`` is ``None`` where no session host composed the operation; no
    frontend exists there to tell apart, so the supplied label stands.
    """
    if reader is None:
        return supplied
    caller = reader(context.identity)
    if caller.frontend is not OperationFrontendProjection.MCP:
        return supplied
    return f"agent:mcp.{caller.session_kind.value}.{caller.client_id}"


__all__ = ["OperationExecutionCaller", "OperationExecutionCallerReader", "execution_actor_label"]
