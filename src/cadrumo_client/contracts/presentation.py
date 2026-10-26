"""A person's request that their own TUI show one register view; it carries no facts and grants nothing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

from .navigation import NavigationSurface, ViewLinkRefusal, load_navigation_register, view_request_refusal

type PresentationRefusal = Literal["not_a_tui_view"] | ViewLinkRefusal
"""Why a view cannot be asked of a TUI: no TUI implements it, or the register refuses the request."""


def presentation_refusal(destination: str, params: Mapping[str, str]) -> PresentationRefusal | None:
    """Return why a TUI may not be asked to show ``destination`` with ``params``, or ``None`` when it may.

    The destination is a register id whose surfaces include the TUI, and the
    parameters are only those the element declares, each a value of its kind.
    Every relay and receiver checks a request through this one function.
    """
    register = load_navigation_register()
    if destination not in register.ids_for(NavigationSurface.TUI):
        return "not_a_tui_view"
    return view_request_refusal(destination, params, register=register)


class PresentationRequest(BaseModel):
    """Ask the runtime to tell this person's TUI on the same profile to show register view ``destination``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["present_destination"] = "present_destination"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    destination: str
    params: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _a_tui_view(self) -> Self:
        refusal = presentation_refusal(self.destination, self.params)
        if refusal is not None:
            raise ValueError(f"destination is not a TUI view request: {refusal}")
        return self


class PresentationDelivered(BaseModel):
    """How many of the person's signed-in TUI connections were sent the request.

    Delivery is queueing on their event streams, not a page the TUI showed:
    the TUI still admits the destination against its own current projection.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    kind: Literal["presentation_delivered"] = "presentation_delivered"
    request_id: UUID
    runtime_boot_id: UUID
    connection_id: UUID
    destination: str
    params: dict[str, str] = Field(default_factory=dict)
    """The request's parameters, echoed so the asker can check which request was delivered."""
    delivered: Annotated[int, Field(ge=0)]
