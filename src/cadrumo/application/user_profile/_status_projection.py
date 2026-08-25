"""Frontend-neutral immutable projection for profile status surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ...core.presentation import NoticePresentation


@dataclass(frozen=True, slots=True)
class StatusFactRow:
    """One safe resolved profile fact prepared for presentation."""

    label: str
    value: str
    masked: bool = False


@dataclass(frozen=True, slots=True)
class StatusProfileRow:
    """One registered profile bucket prepared for presentation."""

    label: str
    setup_state: str | None = None
    active: bool = False


@dataclass(frozen=True, slots=True)
class StatusAuthView:
    """Authentication and unlocked-session facts prepared for presentation."""

    provider: str | None = None
    login_ready: bool = False
    subject: str | None = None
    certificate_source: str | None = None
    idle_deadline: datetime | None = None
    absolute_deadline: datetime | None = None


@dataclass(frozen=True, slots=True)
class StatusPageData:
    """Complete read-only status projection shared by entrypoints."""

    active_profile_label: str | None = None
    facts: tuple[StatusFactRow, ...] = ()
    profiles: tuple[StatusProfileRow, ...] = ()
    auth: StatusAuthView = field(default_factory=StatusAuthView)
    notices: tuple[NoticePresentation, ...] = ()


__all__ = ["StatusAuthView", "StatusFactRow", "StatusPageData", "StatusProfileRow"]
