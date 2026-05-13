"""Application-level live AEAT read workflow errors."""

from __future__ import annotations

from ...core.errors import AeatError


class LiveApplicationError(AeatError):
    """Raised when live AEAT read orchestration fails."""


class LiveApplicationInputError(LiveApplicationError):
    """Raised when a live AEAT read request is not executable."""


__all__ = ["LiveApplicationError", "LiveApplicationInputError"]
