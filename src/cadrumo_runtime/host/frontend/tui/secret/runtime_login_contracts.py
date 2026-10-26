"""Public proof and handoff contracts for runtime login."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum, auto
from uuid import UUID

from cadrumo_client.contracts.profile_access import ProfileStatus
from cadrumo_client.transport.frontend_client import FrontendClient


class RuntimeLoginMethod(StrEnum):
    """The explicitly selected proof family for one runtime login attempt."""

    PASSWORD = auto()
    API_KEY = auto()
    API_REFERENCE = auto()
    RECEIPT = auto()


@dataclass(frozen=True, slots=True)
class RuntimeLoginHandoff:
    """Transfer the one verified connection, without claiming local custody."""

    profile_id: UUID
    profile_label: str
    method: RuntimeLoginMethod
    status: ProfileStatus
    client: FrontendClient = field(repr=False)


type RuntimeClientOpener = Callable[[UUID], Awaitable[FrontendClient]]
type RuntimeCredentialClientOpener = Callable[[UUID, UUID, Callable[[FrontendClient], None]], Awaitable[FrontendClient]]
type RuntimeLoginAcceptor = Callable[[RuntimeLoginHandoff], bool]
