"""Host-owned profile authority at canonical operation execution boundaries."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from pydantic import BaseModel

from ..user_profile.access_contracts import AccessAction
from .models import OperationIdentity, OperationRequest


class OperationExecutionAuthority(Protocol):
    """Revalidate exact operation ownership without replacing supervision or custody.

    The host resolves profile, session, periods and current policy through the
    registered operation owner. Missing authority raises before execution; this
    port never supplies a cached boolean or reconstructs response capabilities.
    """

    async def require[Payload: BaseModel](
        self,
        *,
        identity: OperationIdentity,
        request: OperationRequest[Payload],
        action: AccessAction,
    ) -> None:
        """Reobserve authority for submit, executor entry or checkpoint re-entry."""
        ...

    def commit_guard(self, identity: OperationIdentity) -> AbstractAsyncContextManager[None]:
        """Hold the authority owner's denial fence through a bounded effect boundary."""
        ...


async def invoke_authorized[Payload: BaseModel, Result](
    authority: OperationExecutionAuthority | None,
    *,
    identity: OperationIdentity,
    request: OperationRequest[Payload],
    action: AccessAction,
    executor: Callable[[], Coroutine[None, None, Result]],
) -> Result:
    """Check at actual task entry before constructing the executor coroutine."""
    if authority is not None:
        await authority.require(identity=identity, request=request, action=action)
    return await executor()
