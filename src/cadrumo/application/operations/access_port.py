"""Registered operation-owner resolution of private access coordinates."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from .access_resolution import OperationAccessContext, ResolvedOperationAccess
    from .models import OperationRequest


@runtime_checkable
class OperationAccessResolver(Protocol):
    """Resolve validated operands through their owner, never caller policy claims."""

    def __call__(
        self, request: OperationRequest[BaseModel], context: OperationAccessContext, /
    ) -> ResolvedOperationAccess:
        """Return current coordinates/readiness or raise a typed access refusal."""
        ...
