"""A person's request that their own TUI show one page; it carries no facts and grants nothing."""

from __future__ import annotations

from typing import Annotated, Final, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG

type PresentationDestination = Literal[
    "home",
    "ledger",
    "withholding",
    "declarations",
    "aeat_sync",
    "operations",
    "installation",
    "setup",
    "reference",
    "profile",
    "aeat_auth",
]
"""The closed pages a desktop link may ask the TUI to show; the TUI alone resolves and admits them."""


class PresentationRequest(BaseModel):
    """Ask the runtime to tell this person's TUI on the same profile to show ``destination``."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    action: Literal["present_destination"] = "present_destination"
    request_id: UUID
    profile_id: UUID
    session_id: UUID
    destination: PresentationDestination


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
    destination: PresentationDestination
    delivered: Annotated[int, Field(ge=0)]


_NIL_PROFILE: Final = UUID(int=0)


def destination_link(profile_id: UUID, destination: PresentationDestination) -> str:
    """Spell the desktop link that asks this profile's TUI to show ``destination``.

    The link grammar is exact: a lowercase, non-nil profile UUID and the page
    word, which writes the destination's underscores as hyphens.
    """
    if profile_id == _NIL_PROFILE:
        raise ValueError("a page link names a real profile")
    return f"cadrumo://profiles/{profile_id}/{destination.replace('_', '-')}"
