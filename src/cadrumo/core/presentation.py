"""Layer-neutral immutable presentation contracts shared by entrypoints."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NoticePresentation:
    """Already-resolved notice facts safe for inert presentation widgets."""

    severity: str
    message: str
    action_target: str | None = None


__all__ = [
    "NoticePresentation",
]
