"""Capability-selecting frontend runner for the setup wizard.

This entrypoint-layer seam is what lets ``aeat config profile create`` and
``edit`` render on the full-screen Textual flow while the wizard command
factory (an application-layer module) stays free of an inbound-adapter
import: the entrypoint may reach ``adapters.inbound.tui``, the application
layer may not. The application default renders the line-mode frontend; the
runner built here is injected into
:func:`~cadrumo.application.wizard.build_wizard_command` so the paged flow
is the operator-facing default in a capable terminal.

Selection tiers:

* FULL_SCREEN — a capable interactive console hosts the full-screen
  :func:`~cadrumo.adapters.inbound.tui.run_flow_tui`.
* LINE — a host that cannot run the full-screen application degrades to
  the line-mode frontend over the identical engine, validation, and
  submit gate; only the rendering differs.
* NON_INTERACTIVE — a piped / no-console host cannot host either
  frontend, so the run refuses with the flow substrate's translated
  no-console error, which the wizard maps to its create / edit hint.

The capability probe is a THIN LOCAL SEAM. The campaign's substrate
stream is landing ``detect_frontend_capability`` (in
``cadrumo.application.flows``) and ``select_flow_frontend`` (in
``cadrumo.adapters.inbound.tui``); when those symbols reach HEAD this
module's local ``_FrontendCapability`` / ``_detect_capability`` /
``_select_and_run`` collapse to a one-line delegation to them.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ....application.flows import FlowDefinition, FlowState
    from ....core.flows import FlowMode


class _FrontendCapability(StrEnum):
    """The three rendering tiers a host can support.

    Neutral local mirror of the incoming
    ``cadrumo.core.flows.FrontendCapability`` contract; kept minimal so
    the swap to the shipped enum is mechanical.
    """

    FULL_SCREEN = "full_screen"
    LINE = "line"
    NON_INTERACTIVE = "non_interactive"


def _detect_capability(definition: FlowDefinition) -> _FrontendCapability:
    """Classify the current host's flow-rendering capability.

    LOCAL SEAM: reuses the flow substrate's own console probe (the
    line-mode frontend's ``ensure_interactive_environment``, the sanctioned
    non-TTY / Windows-no-console detection) to separate an interactive
    console from a piped / no-console host. The FULL_SCREEN vs LINE
    distinction (a terminal that hosts basic prompts but not a full-screen
    application) awaits the substrate stream's Textual-aware
    ``detect_frontend_capability``; until then a capable console is treated
    as full-screen and LINE is reachable only when the shipped contract
    lands.
    """
    from ....application.flows import FlowUnsupportedConsoleError, LineFlowFrontend

    try:
        LineFlowFrontend(definition).ensure_interactive_environment()
    except FlowUnsupportedConsoleError:
        return _FrontendCapability.NON_INTERACTIVE
    return _FrontendCapability.FULL_SCREEN


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
    from ....application.flows import FlowUnsupportedConsoleError, LineFlowFrontend

    capability = _detect_capability(definition)
    if capability is _FrontendCapability.NON_INTERACTIVE:
        raise FlowUnsupportedConsoleError(translated_message="flows.errors.unsupported_console")
    if capability is _FrontendCapability.LINE:
        state, _projection = LineFlowFrontend(definition).run(mode=mode)
        return state

    from ....adapters.inbound.tui import run_flow_tui

    state, _projection = run_flow_tui(definition, mode=mode, registered_values=registered_values)
    return state


__all__ = ["run_setup_flow_frontend"]
