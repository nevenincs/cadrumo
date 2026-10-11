"""The handlers the installation door serves, keyed by the request each one takes.

A handler is registered for the request type of exactly one act. An act with
no registered handler is answered as unavailable, so the door can be served
before every act has a handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import BaseModel

from ...application.runtime.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    RuntimeInstallationActRequest,
    installation_act_of,
)
from ...core.errors.hierarchy import InternalInvariantError

if TYPE_CHECKING:
    from .installation_door import InstallationActHandler


class InstallationActRegistry:
    """One handler for each act that has one."""

    def __init__(self) -> None:
        """Start with no act served."""
        self._handlers: dict[InstallationAct, InstallationActHandler[BaseModel]] = {}

    def register[RequestT: BaseModel](
        self, request_type: type[RequestT], handler: InstallationActHandler[RequestT]
    ) -> None:
        """Serve the act whose request is ``request_type`` with ``handler``.

        Raises:
            InternalInvariantError: ``request_type`` is not the request of an
                installation act, or that act already has a handler.
        """
        act = next(
            (contract.act for contract in INSTALLATION_ACT_CONTRACTS.values() if contract.request is request_type),
            None,
        )
        if act is None:
            raise InternalInvariantError("a handler is registered for the request of an installation act")
        if act in self._handlers:
            raise InternalInvariantError("an installation act has exactly one handler")
        # The table key is the exact request type, so the door only ever hands
        # this handler the request it declared.
        self._handlers[act] = cast("InstallationActHandler[BaseModel]", handler)

    def handler_for(self, request: RuntimeInstallationActRequest) -> InstallationActHandler[BaseModel] | None:
        """Return the handler of the act ``request`` asks for, or ``None`` when it has none."""
        return self._handlers.get(installation_act_of(request))

    @property
    def served_acts(self) -> frozenset[InstallationAct]:
        """Name every act that has a handler."""
        return frozenset(self._handlers)


def production_installation_acts() -> InstallationActRegistry:
    """Compose the handlers the installed runtime serves."""
    return InstallationActRegistry()
