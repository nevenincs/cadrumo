"""The handlers the installation door serves, keyed by the request each one takes.

A handler is registered for the request type of exactly one act. An act with
no registered handler is answered as unavailable, so the door can be served
before every act has a handler.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pydantic import BaseModel

from cadrumo.core.errors.hierarchy import InternalInvariantError
from cadrumo_client.contracts.installation_requests import (
    INSTALLATION_ACT_CONTRACTS,
    InstallationAct,
    InstallationActRequest,
    installation_act_of,
)

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

    def handler_for(self, request: InstallationActRequest) -> InstallationActHandler[BaseModel] | None:
        """Return the handler of the act ``request`` asks for, or ``None`` when it has none."""
        return self._handlers.get(installation_act_of(request))

    @property
    def served_acts(self) -> frozenset[InstallationAct]:
        """Name every act that has a handler."""
        return frozenset(self._handlers)


def production_installation_acts() -> InstallationActRegistry:
    """Compose the handlers the installed runtime serves: every act of the table, one family at a time."""
    # Each family registers on the registry this module defines, so a family
    # loads only once the registry exists.
    from .installation_artefacts import register_artefact_acts
    from .installation_profiles import register_profile_acts
    from .installation_repair import register_repair_acts
    from .installation_reset import register_reset_acts
    from .installation_storage import register_storage_acts

    registry = InstallationActRegistry()
    register_storage_acts(registry)
    register_reset_acts(registry)
    register_repair_acts(registry)
    register_profile_acts(registry)
    register_artefact_acts(registry)
    return registry
