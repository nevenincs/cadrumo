"""Durable denial contracts shared by profile lifecycle and protected custody."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .access_contracts import ProfileAccessBinding


class AutomationDenialKind(StrEnum):
    """Reduction of authority; none of these changes can enable access."""

    KEY = "key"
    GRANT = "grant"
    ALL = "all"
    PROFILE_LOCK = "profile_lock"


class AutomationDenial(BaseModel):
    """Exact authorized change, safe to retain as a pending denial intent."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    binding: ProfileAccessBinding
    kind: AutomationDenialKind
    target_id: UUID | None = None

    @model_validator(mode="after")
    def _target(self) -> AutomationDenial:
        if (self.kind in {AutomationDenialKind.KEY, AutomationDenialKind.GRANT}) != (self.target_id is not None):
            raise ValueError("denial target does not match action")
        return self


class AutomationDenialReceipt(BaseModel):
    """Durable denial is distinct from completed native credential cleanup."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    request_id: UUID
    profile_id: UUID
    access_denied: bool
    cleanup_pending: bool
    revision: Annotated[int, Field(ge=1)] | None
    profile_lock_generation: Annotated[int, Field(ge=0)] | None


class ProfileGlobalLockState(BaseModel):
    """Local human-access fence; never proof that automation can unwrap custody."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding: ProfileAccessBinding
    generation: Annotated[int, Field(ge=0)]
    globally_locked: bool


class AutomationDenialCustody(Protocol):
    """Persist denial before attempting optional native-store cleanup."""

    def deny(self, change: AutomationDenial) -> AutomationDenialReceipt:
        """Durably fence, advance protected state and retire affected unwrap keys."""
        ...

    def reconcile_denial(self) -> AutomationDenialReceipt | None:
        """Retry the exact surviving intent; never discard it to enable access."""
        ...

    def profile_lock_state(self) -> ProfileGlobalLockState:
        """Read the local lock without depending on optional native credentials."""
        ...

    def unlock_profile(self, *, generation: int) -> ProfileGlobalLockState:
        """Consume an owner-authorized unlock; leave automation custody unchanged."""
        ...
