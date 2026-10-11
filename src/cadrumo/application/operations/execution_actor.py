"""The actor label an executing operation records for what it writes.

An operation stores who acted in its reports and events. Nothing authenticates
a label a request carries, so the label of an agent's execution is taken from
the session that admitted it, and a person's execution keeps the label the
person's frontend supplied.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final
from uuid import UUID

from ..user_profile.access_contracts import SessionKind
from .models import OperationIdentity
from .registry import OperationFrontendProjection

if TYPE_CHECKING:
    from .owner import OperationExecutorContext

_AGENT_LABEL_PREFIX: Final = "agent:mcp."


@dataclass(frozen=True, slots=True)
class OperationExecutionCaller:
    """The frontend one executing invocation was admitted on, and the session carrying it."""

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
    return f"{_AGENT_LABEL_PREFIX}{caller.session_kind.value}.{caller.client_id}"


def actor_label_is_an_agents(label: str) -> bool:
    """Return whether a recorded actor label is the one an agent's execution records.

    A stored record keeps the label and not the frontend, so what a later
    decision knows of who acted is this label. An agent's execution cannot
    record another: its label comes from its session. A person's frontend
    records the label it supplies, so a person who types this form records
    their own act as an agent's.
    """
    return label.startswith(_AGENT_LABEL_PREFIX)


__all__ = [
    "OperationExecutionCaller",
    "OperationExecutionCallerReader",
    "actor_label_is_an_agents",
    "execution_actor_label",
]
