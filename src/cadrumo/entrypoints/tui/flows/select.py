"""The single frontend-selection primitive: capability in, frontend out.

A consumer that has already classified the host with
:func:`~cadrumo.application.flows.detect_frontend_capability` calls this to
receive the constructed frontend for that capability — the full-screen
Textual app or the line-mode frontend — without re-deciding. A
non-interactive host refuses here: a scripted caller that has answers to
replay drives :func:`~cadrumo.application.flows.run_scripted_flow` itself
and never routes through this selector.

This module lives in the entrypoint tier because it may name the Textual
application; the application layer must not. Consumers import this canonical
projection directly rather than through a package facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ....application.flows import FlowUnsupportedConsoleError, LineFlowFrontend
from ....core.flows import FrontendCapability
from .app import FlowTuiApp

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.flows import CheckpointStore, FlowDefinition, FlowState
    from ....core.flows import FlowMode


def select_flow_frontend(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    capability: FrontendCapability,
    checkpoint_store: CheckpointStore | None = None,
    resume_state: FlowState | None = None,
    registered_values: Mapping[str, str] | None = None,
) -> FlowTuiApp | LineFlowFrontend:
    """Construct the frontend the host's ``capability`` supports.

    Returns a :class:`FlowTuiApp` for
    :attr:`~cadrumo.core.flows.FrontendCapability.FULL_SCREEN` and a
    :class:`~cadrumo.application.flows.LineFlowFrontend` for
    :attr:`~cadrumo.core.flows.FrontendCapability.LINE`. A
    :attr:`~cadrumo.core.flows.FrontendCapability.NON_INTERACTIVE` host
    refuses with :class:`~cadrumo.application.flows.FlowUnsupportedConsoleError`
    — there is no interactive frontend to hand back.
    """
    if capability is FrontendCapability.NON_INTERACTIVE:
        raise FlowUnsupportedConsoleError(
            translated_message="flows.errors.unsupported_console",
        )
    if capability is FrontendCapability.FULL_SCREEN:
        return FlowTuiApp(
            definition,
            mode=mode,
            checkpoint_store=checkpoint_store,
            resume_state=resume_state,
            registered_values=registered_values,
        )
    return LineFlowFrontend(definition, checkpoint_store=checkpoint_store)


__all__ = ["select_flow_frontend"]
