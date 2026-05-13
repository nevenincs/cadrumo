"""Errors for the backend-owned operator surface contract."""

from __future__ import annotations

from ...core.errors import AeatError


class OperatorSurfaceContractError(AeatError):
    """Raised when a caller requests a surface outside the accepted contract."""

    def __init__(self, surface: str, *, reason: str, suggestion: str | None = None) -> None:
        super().__init__(
            f"operator surface {surface!r} is not part of the accepted contract: {reason}",
            context={"surface": surface, "reason": reason},
            suggestion=suggestion,
        )
        self.surface = surface
        self.reason = reason
