"""Errors for the backend-owned operator surface contract."""

from __future__ import annotations

from ...core.errors import AeatError
from ...core.i18n import tr


class OperatorSurfaceContractError(AeatError):
    """Raised when a caller requests a surface outside the accepted contract."""

    def __init__(self, surface: str, *, reason: str, suggestion: str | None = None) -> None:
        super().__init__(
            tr(
                "cli.operator_surface.errors.contract_not_accepted",
                default="operator surface contract rejected %{surface}: %{reason}",
                surface=repr(surface),
                reason=reason,
            ),
            context={"surface": surface, "reason": reason},
            suggestion=suggestion,
        )
        self.surface = surface
        self.reason = reason
