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
    from collections.abc import Callable, Mapping

    from ....adapters.inbound.tui import FlowTuiApp
    from ....application.flows import CheckpointStore, FlowDefinition, FlowState
    from ....core.flows import FlowMode


def _line_committed_callback(
    on_language_activated: Callable[[str, str], bool] | None,
) -> Callable[[str, str], None] | None:
    """Adapt the language activator to the line frontend's post-commit callback.

    Line mode re-assembles every page's copy on render, so an activated
    language surfaces on the next page with no explicit rebuild; the
    activator's verdict is therefore discarded here.
    """
    if on_language_activated is None:
        return None

    def _committed(page_key: str, value: str) -> None:
        on_language_activated(page_key, value)

    return _committed


def run_setup_flow_frontend(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    registered_values: Mapping[str, str] | None,
    on_language_activated: Callable[[str, str], bool] | None = None,
    checkpoint_store: CheckpointStore | None = None,
) -> FlowState:
    """Drive ``definition`` on the best frontend the host supports.

    ``on_language_activated`` is the mid-walk output-language activator (see
    :func:`cadrumo.application.wizard.build_wizard_command`). It is fired
    post-commit on each answered page and re-activates the output language
    when the ``output-language`` page is committed, so the remaining pages
    render in the chosen language. It is ``None`` when an explicit flag or the
    environment already pins the language, in which case no hook is wired.

    ``checkpoint_store`` backs create-mode save-and-exit; both frontends
    honour it identically when the definition declares checkpointing
    AVAILABLE for ``mode``.

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
        state, _projection = LineFlowFrontend(
            definition,
            checkpoint_store=checkpoint_store,
            on_answer_committed=_line_committed_callback(on_language_activated),
        ).run(mode=mode)
        return state

    from ....adapters.inbound.tui import run_flow_tui

    if on_language_activated is None:
        state, _projection = run_flow_tui(
            definition,
            mode=mode,
            registered_values=registered_values,
            checkpoint_store=checkpoint_store,
        )
        return state

    return _run_full_screen_with_locale_hook(
        definition,
        mode=mode,
        registered_values=registered_values,
        on_language_activated=on_language_activated,
        checkpoint_store=checkpoint_store,
    )


def _run_full_screen_with_locale_hook(
    definition: FlowDefinition,
    *,
    mode: FlowMode,
    registered_values: Mapping[str, str] | None,
    on_language_activated: Callable[[str, str], bool],
    checkpoint_store: CheckpointStore | None = None,
) -> FlowState:
    """Run the full-screen frontend with the mid-walk locale-switch hook wired.

    The hook calls :meth:`FlowTuiApp.rebuild_for_locale` after activating the
    language so the mounted screen (its footer bindings included) re-resolves
    under the new locale. The app handle arrives through ``on_app_ready``, so
    the runner keeps ownership of the app lifecycle and its abandoned-run
    guard. ``checkpoint_store`` backs create-mode save-and-exit.
    """
    from ....adapters.inbound.tui import run_flow_tui

    holder: dict[str, FlowTuiApp] = {}

    def _committed(page_key: str, value: str) -> None:
        if on_language_activated(page_key, value):
            holder["app"].rebuild_for_locale()

    state, _projection = run_flow_tui(
        definition,
        mode=mode,
        registered_values=registered_values,
        checkpoint_store=checkpoint_store,
        on_answer_committed=_committed,
        on_app_ready=lambda app: holder.__setitem__("app", app),
    )
    return state


__all__ = ["run_setup_flow_frontend"]
