"""Frontend-capability detection: one probe, one classification.

A flow consumer must decide which frontend a host can present before it
constructs one. This module owns that decision as a single function so
every consumer selects in one place, and owns the single
``prompt_toolkit`` no-console probe (:data:`NO_CONSOLE_ERRORS`) the
line-mode frontend also imports — there is one console-capability probe
in the substrate, not two.

The module imports no rendering library beyond the guarded win32
``prompt_toolkit`` probe (the same pattern the line frontend used), so it
stays free of Textual and questionary.
"""

from __future__ import annotations

import os
import sys

from ...core.flows import FrontendCapability
from ...core.logging import get_logger
from ...core.tty import stdin_is_tty, stdout_is_tty

_log = get_logger(__name__)


def _resolve_no_console_error_types() -> tuple[type[BaseException], ...]:
    """Return the prompt_toolkit error classes that signal an unsupported console host."""
    error_types: list[type[BaseException]] = [OSError]
    if sys.platform != "win32":
        return tuple(error_types)
    try:
        from prompt_toolkit.output.win32 import NoConsoleScreenBufferError as _Win32NoConsole
    except ImportError as exc:
        _log.debug("flows capability: win32 console probe unavailable: %s", exc)
        return tuple(error_types)
    else:
        # Bound in the else branch so the success scope is explicit: on a non-Windows
        # host the module does not exist at all, and a checker analysing that platform
        # otherwise reads the name as never bound.
        error_types.insert(0, _Win32NoConsole)
        return tuple(error_types)


NO_CONSOLE_ERRORS: tuple[type[BaseException], ...] = _resolve_no_console_error_types()
"""prompt_toolkit error classes signalling a host that cannot open a console.

``NoConsoleScreenBufferError`` (git-bash / redirected console on Windows)
is not an ``OSError`` subclass, so it is enumerated explicitly ahead of
``OSError``."""


def detect_frontend_capability(*, override: FrontendCapability | None = None) -> FrontendCapability:
    """Classify how richly the current host can present an interactive flow.

    ``override`` short-circuits detection (an operator flag, a test). A
    host whose stdin or stdout is not a real TTY, or that advertises a dumb
    terminal (``TERM=dumb``, the CI default) is
    :attr:`~cadrumo.core.flows.FrontendCapability.NON_INTERACTIVE`. A host
    with a TTY where the full-screen console buffer cannot start (the
    ``NoConsoleScreenBufferError`` class, git-bash on Windows) degrades to
    :attr:`~cadrumo.core.flows.FrontendCapability.LINE`; otherwise the
    full-screen frontend is hostable.
    """
    if override is not None:
        return override
    if os.environ.get("TERM", "").strip().lower() == "dumb":
        return FrontendCapability.NON_INTERACTIVE
    if not (stdin_is_tty() and stdout_is_tty()):
        return FrontendCapability.NON_INTERACTIVE
    try:
        from prompt_toolkit.output.defaults import create_output

        output = create_output(always_prefer_tty=True)
        output.flush()
    except NO_CONSOLE_ERRORS as exc:
        _log.debug("flows capability: full-screen host unavailable, degrading to line mode: %s", exc)
        return FrontendCapability.LINE
    return FrontendCapability.FULL_SCREEN


__all__ = ["NO_CONSOLE_ERRORS", "detect_frontend_capability"]
