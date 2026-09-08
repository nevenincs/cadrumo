"""Shared ``prompt_toolkit`` no-console error classification.

The module imports no rendering library beyond the guarded win32
``prompt_toolkit`` probe (the same pattern the line frontend used), so it
stays free of Textual and questionary.
"""

from __future__ import annotations

import sys

from ...core.logging import get_logger

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


__all__ = ["NO_CONSOLE_ERRORS"]
