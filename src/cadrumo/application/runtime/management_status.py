"""Credential-free runtime management observations, never access authority."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .management import RuntimeManagerInspection


class RuntimeListenerState(StrEnum):
    """What an exact peer-verified listener observation established."""

    READY = "ready"
    DRAINING = "draining"
    UNAVAILABLE = "unavailable"
    REFUSED = "refused"
    UNKNOWN = "unknown"


class RuntimeManagerAvailability(StrEnum):
    """Manager inspection is distinct from login autostart and profile grants."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    REFUSED = "refused"
    UNKNOWN = "unknown"


class RuntimeManagementSnapshot(BaseModel):
    """Public nonsecret status without executable, root, owner or grant claims."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    listener: RuntimeListenerState
    manager_availability: RuntimeManagerAvailability
    manager: RuntimeManagerInspection | None = None

    @model_validator(mode="after")
    def _consistent_manager(self) -> RuntimeManagementSnapshot:
        if self.manager_availability is RuntimeManagerAvailability.AVAILABLE:
            if self.manager is None or not self.manager.available:
                raise ValueError("available manager requires its inspected facts")
        elif self.manager_availability is RuntimeManagerAvailability.UNAVAILABLE:
            if self.manager is not None and self.manager.available:
                raise ValueError("unavailable manager cannot carry available facts")
        elif self.manager is not None:
            raise ValueError("uninspected manager cannot carry asserted facts")
        return self


__all__ = ["RuntimeListenerState", "RuntimeManagementSnapshot", "RuntimeManagerAvailability"]
