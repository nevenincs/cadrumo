"""Errors for the backend-owned operator-surface contract.

:class:`OperatorSurfaceContractError` is the registered
:class:`~aeat.core.errors.AeatError` raised by
:func:`~aeat.application.operator_surface.require_accepted_root` and
:func:`~aeat.application.operator_surface.resolve_source_kind_alias` when a
caller asks for a root, source-kind token, or command-surface shape outside the
accepted :class:`~aeat.application.operator_surface.OperatorSurfaceContract`.
The application error registry binds it to ``REFUSED_OPERATOR_SURFACE_CONTRACT``
so boundary adapters can render the refusal through the shared error contract.
"""

from __future__ import annotations

from ...core.errors import AeatError
from ...core.i18n import tr


class OperatorSurfaceContractError(AeatError):
    """Registered application error for rejected operator-surface requests.

    The message is localized with a stable, non-secret ``surface`` / ``reason``
    context payload, and optional ``suggestion`` text gives callers the accepted
    follow-up command. Raw operator input is stored only in structured context
    for the central error renderer to handle consistently.
    """

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
