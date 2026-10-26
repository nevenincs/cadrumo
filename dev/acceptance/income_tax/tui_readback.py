"""Read rendered public workbench state without crossing application boundaries."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .tui_contracts import TuiJourneyError
from .tui_selectors import _FIRST_OPEN_GREETING, WORKBENCH_NOTICE

if TYPE_CHECKING:
    from textual.pilot import Pilot
    from textual.widget import Widget


def _rendered_text(widget: object) -> str:
    """Read a widget's public rendered content without serializing raw data."""
    render = getattr(widget, "render", None)
    if not callable(render):
        raise TuiJourneyError("installed TUI control exposes no rendered text")
    return str(render()).strip()


def _query_visible_tui_control(pilot: Pilot[Any], selector: str) -> Widget:
    """Resolve a public control on the top screen, the only one an operator can act on."""
    return pilot.app.screen.query_one(selector)


def workbench_notice(pilot: Pilot[Any]) -> str:
    """Read the workbench's notice, even while a dialog it opened sits above it."""
    return _stack_text(pilot, WORKBENCH_NOTICE)


def _stack_text(pilot: Pilot[Any], selector: str) -> str:
    """Read the rendered text of the top-most screen that shows ``selector``, or nothing.

    The workbench's notice stays on the workbench while a dialog it opened
    sits above it, so it is read from the nearest screen down the stack that
    has it.  The greeting the first workbench of a session shows there, until
    the filer's first key, reports nothing, so it reads as no notice.
    """
    from textual.css.query import NoMatches

    from cadrumo.core.i18n.render import tr

    for screen in reversed(pilot.app.screen_stack):
        try:
            text = _rendered_text(screen.query_one(selector))
        except NoMatches:
            continue
        if selector == WORKBENCH_NOTICE and text == tr(_FIRST_OPEN_GREETING):
            return ""
        return text
    return ""
