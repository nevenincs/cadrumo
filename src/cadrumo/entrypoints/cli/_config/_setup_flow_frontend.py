"""Capability-selecting frontend runner for the setup wizard.

This entrypoint-layer seam is what lets ``aeat config profile create`` and
``edit`` render on the full-screen Textual flow while the wizard command
factory (an application-layer module) stays free of an inbound-adapter
import: the entrypoint may reach ``adapters.inbound.tui``, the application
layer may not. The application default renders the line-mode frontend; the
runner built here is injected into
:func:`~cadrumo.application.wizard.build_wizard_command` so the paged flow
is the operator-facing default in a capable terminal.

Selection tiers, classified by the flow substrate's own
:func:`~cadrumo.application.flows.detect_frontend_capability` (the single
probe authority — never re-derived here):

* FULL_SCREEN — a capable interactive console hosts the full-screen
  :func:`~cadrumo.adapters.inbound.tui.run_flow_tui`.
* LINE — a host that cannot run the full-screen application degrades to
  the line-mode frontend over the identical engine, validation, and
  submit gate; only the rendering differs.
* NON_INTERACTIVE — a piped / no-console host cannot host either
  frontend, so the run refuses with the flow substrate's translated
  no-console error, which the wizard maps to its create / edit hint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.flows import FlowDefinition, FlowState
    from ....core.flows import FlowMode


def run_setup_flow_frontend(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    registered_values: Mapping[str, str] | None,
) -> FlowState:
    """Drive ``definition`` on the best frontend the host supports.

    Raises:
        FlowUnsupportedConsoleError: When the host can host neither the
            full-screen nor the line frontend; the wizard command maps
            this to its create / edit no-console hint.
    """
    from ....application.flows import (
        FlowUnsupportedConsoleError,
        LineFlowFrontend,
        detect_frontend_capability,
    )
    from ....core.flows import FrontendCapability

    capability = detect_frontend_capability()
    if capability is FrontendCapability.NON_INTERACTIVE:
        raise FlowUnsupportedConsoleError(translated_message="flows.errors.unsupported_console")
    if capability is FrontendCapability.LINE:
        state, _projection = LineFlowFrontend(definition).run(mode=mode)
        return state

    from ....adapters.inbound.tui import run_flow_tui

    state, _projection = run_flow_tui(definition, mode=mode, registered_values=registered_values)
    return state


__all__ = ["run_setup_flow_frontend"]
