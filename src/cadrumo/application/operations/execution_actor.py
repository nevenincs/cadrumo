"""The actor label an executing operation records for what it writes.

An operation stores who acted in its reports and events. Nothing authenticates
a label a request carries, so the label of an automation's execution is taken from
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
from .person_acts import is_persons_frontend
from .registry import OperationFrontendProjection

if TYPE_CHECKING:
    from .owner import OperationExecutorContext

_AUTOMATION_LABEL_PREFIXES: Final = tuple(
    f"automation:{frontend.value}." for frontend in OperationFrontendProjection if not is_persons_frontend(frontend)
)


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

    An execution admitted on an automation's frontend is an automation's. Its label
    names the frontend, the session's kind and client, and the label the
    request supplied is not recorded. The person's frontends record the
    supplied label unchanged.

    ``reader`` is ``None`` where no session host composed the operation; no
    frontend exists there to tell apart, so the supplied label stands.
    """
    if reader is None:
        return supplied
    caller = reader(context.identity)
    if is_persons_frontend(caller.frontend):
        return supplied
    return f"automation:{caller.frontend.value}.{caller.session_kind.value}.{caller.client_id}"


def actor_label_is_automation(label: str) -> bool:
    """Return whether a recorded actor label is the one an automation's execution records.

    A stored record keeps the label and not the frontend, so what a later
    decision knows of who acted is this label. An automation's execution cannot
    record another: its label comes from its session. A person's frontend
    records the label it supplies, so a person who types this form records
    their own act as an automation's.
    """
    return label.startswith(_AUTOMATION_LABEL_PREFIXES)


__all__ = [
    "OperationExecutionCaller",
    "OperationExecutionCallerReader",
    "actor_label_is_automation",
    "execution_actor_label",
]
