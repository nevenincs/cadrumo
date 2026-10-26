"""Whether helper children started by this process share its console.

A supervised runtime is stopped by a console Ctrl+C that its manager sends to
the runtime's console. Windows delivers that event to every process attached
to the console, so a helper child that shares it would be interrupted beside
the runtime instead of being settled by the runtime's drain. The supervised
entrypoint therefore isolates helper children once, at startup, for the rest
of the process. The console is process-wide state, so the choice is bound
process-wide: every helper launch site observes it, whichever thread or
composed port reaches that site.

Isolation uses ``CREATE_NO_WINDOW``, which gives the child a console of its
own without a window. ``CREATE_NEW_PROCESS_GROUP`` is never used here because
it also makes the child ignore Ctrl+C. Workers are launched with their own
console by their native launcher and do not consult this module.
"""

from __future__ import annotations

import sys
from enum import StrEnum
from typing import Final

from .process_binding import ProcessScopedBinding

# CREATE_NO_WINDOW, spelled as a literal so the value is defined on every platform.
WINDOWS_CREATE_NO_WINDOW: Final = 0x08000000


class ChildConsole(StrEnum):
    """Which console a helper child started by this process attaches to."""

    SHARED = "shared"
    OWN = "own"


# Bound process-wide by the supervised entrypoint through isolate_child_consoles.
child_console_binding: Final[ProcessScopedBinding[ChildConsole]] = ProcessScopedBinding("cadrumo_child_console")


def isolate_child_consoles() -> None:
    """Give every helper child started from now on a console of its own."""
    child_console_binding.bind(ChildConsole.OWN)


def child_console() -> ChildConsole:
    """Return the console helper children of this process attach to."""
    return child_console_binding.get() or ChildConsole.SHARED


def child_console_creation_flags() -> int:
    """Return the Windows creation flags a helper child launch must carry.

    The result is ``0`` outside Windows and in a process that shares its
    console, so the launch is unchanged there.
    """
    if sys.platform != "win32" or child_console() is ChildConsole.SHARED:
        return 0
    return WINDOWS_CREATE_NO_WINDOW


__all__ = [
    "WINDOWS_CREATE_NO_WINDOW",
    "ChildConsole",
    "child_console",
    "child_console_binding",
    "child_console_creation_flags",
    "isolate_child_consoles",
]
