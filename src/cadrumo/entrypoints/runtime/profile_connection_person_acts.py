"""Refuse on an agent's frontend the requests that are the person's own act.

An agent works only inside the one profile the person signed in to, or one the
person issued a key for, and never authenticates, administers sessions or
access, or handles a secret. The MCP harness offers no tool that sends any of
these requests, which is the decisive control. The frontend a request names is
a client's claim, so this refusal is defence in depth, keyed on the act: each
request listed in :mod:`cadrumo.application.operations.person_acts` is refused
here when it arrives on any frontend that is not the person's, with one typed
code that tells the agent to have the person act in Cadrumo.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ...adapters.local_runtime.runtime_frame_io import write_document
from ...application.operations.person_acts import is_persons_frontend
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.contracts import RuntimeByteChannel
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError

if TYPE_CHECKING:
    from uuid import UUID

    from .profile_connections import RuntimeProfileConnections

_WRITE_SECONDS = 5


class ProfileConnectionPersonActMixin:
    """Refuse the person's acts on an agent's frontend, wherever the runtime's door receives one."""

    def _require_persons_frontend(self: RuntimeProfileConnections, frontend: OperationFrontendProjection) -> None:
        """Refuse a person's act that names an agent's frontend, with the code that sends the agent to the person."""
        if not is_persons_frontend(frontend):
            raise ProfileAccessRefusedError(AccessDenialCode.PERSON_ACT_REQUIRED)

    def _connection_frontend(
        self: RuntimeProfileConnections, context: RuntimeConnectionContext
    ) -> OperationFrontendProjection | None:
        """Return the frontend this connection logged in with, or ``None`` before it has."""
        with self._guard:
            connection = self._connections.get(context.connection_id)
        return None if connection is None else connection.frontend

    def _refused_as_persons_act(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        *,
        request_id: UUID,
        frontend: OperationFrontendProjection | None,
    ) -> bool:
        """Answer a person's act from an agent's frontend with the typed refusal, and say whether it was refused.

        ``frontend`` is the one the request names, or else the one its
        connection logged in with; a request whose connection has not logged
        in names none and is left to its own door.
        """
        try:
            if frontend is not None:
                self._require_persons_frontend(frontend)
        except ProfileAccessRefusedError as refused:
            write_document(
                channel,
                RuntimeAccessRefusal(
                    request_id=request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    code=refused.reason,
                ),
                deadline=time.monotonic() + _WRITE_SECONDS,
            )
            return True
        return False
