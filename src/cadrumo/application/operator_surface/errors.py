"""Errors for the backend-owned operator-surface contract.

:class:`OperatorSurfaceContractError` is the registered
:class:`~core.errors.CadrumoError` raised when a command-surface declaration
falls outside the accepted operator-surface contract.
The application error registry binds it to ``REFUSED_OPERATOR_SURFACE_CONTRACT``
so boundary adapters can render the refusal through the shared error contract.
"""

from __future__ import annotations

from ...core.errors.hierarchy import CadrumoError, TerminalPreconditionErrorMixin
from ...core.i18n import tr
from ..operator_actions.models import PreconditionVerdict


class OperatorSurfaceContractError(TerminalPreconditionErrorMixin[PreconditionVerdict], CadrumoError):
    """Registered application error for rejected operator-surface requests.

    The message is localized with a stable, non-secret ``surface`` / ``reason``
    context payload. Raw operator input is stored only in structured context
    for the central error renderer to handle consistently.
    """

    def __init__(
        self,
        surface: str,
        *,
        reason: str,
        precondition_verdict: PreconditionVerdict | None = None,
    ) -> None:
        """Initialize this public contract."""
        super().__init__(
            tr(
                "cli.operator_surface.errors.contract_not_accepted",
                default="operator surface contract rejected %{surface}: %{reason}",
                surface=repr(surface),
                reason=reason,
            ),
            context={"surface": surface, "reason": reason},
            precondition_verdict=precondition_verdict,
        )
        self.surface = surface
        self.reason = reason
