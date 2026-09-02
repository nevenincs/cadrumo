"""The one terminal-attachment probe, usable from every layer.

Whether a stream is attached to an interactive terminal is asked by the CLI,
by adapters that must refuse a non-interactive flow (Google OAuth consent, the
master-key passphrase prompt), and by recovery enrollment. The probe itself is
layer-free, so it lives in ``core`` where all of them may import it.

It lived in ``entrypoints/cli/_tty.py`` first, which made it unreachable for
the adapters that needed it most: ``entrypoints`` is the TOP layer of the
hexagonal contract, so nothing beneath it may import from there. Each caller
therefore open-coded ``sys.stdin.isatty()`` instead, and the CLI module's
docstring went on claiming to centralise "the rules every CLI command uses"
while nothing imported it at all. The primitive moved down; the CLI keeps the
policy built on top of it (colour, progress widgets, typed refusals).

**Bare ``stream.isatty()`` is not equivalent to these helpers.** It raises
rather than answering when the stream is missing, closed, or detached — the
precise conditions a headless or service host presents, which is when the
question is being asked. These helpers answer ``False`` instead, so a caller
guarding an interactive flow refuses cleanly rather than dying inside its own
guard.

A truthy answer here is necessary but NOT always sufficient. On Windows both
the ``NUL`` device and a console-less host can report ``isatty() is True``
while no console exists to type into, so a caller that must genuinely read
from a console pairs this with a real-console probe (see
``entrypoints/cli/config/secure_input.py``) rather than replacing that
stricter check with this one.
"""

from __future__ import annotations

import sys
from typing import IO, Any

__all__ = [
    "stderr_is_tty",
    "stdin_is_tty",
    "stdout_is_tty",
    "stream_is_tty",
]


# ANY-RETURN-RATIONALE-STREAM-DUCK-TYPE: accepts any stream-like object by
# design (real streams, closed streams, non-stream objects) and probes it
# structurally via getattr/hasattr rather than a concrete stream protocol.
def stream_is_tty(stream: IO[Any] | object | None) -> bool:
    """Return whether ``stream`` is attached to an interactive terminal.

    Answers ``False`` — never raises — for a stream that is ``None``, exposes
    no callable ``isatty``, has been closed (``ValueError``), or whose
    ``isatty()`` fails at the OS level (``OSError``). Every one of those means
    "no terminal here" for the caller's purpose, and a probe guarding an
    interactive flow must not itself be the thing that raises.

    Args:
        stream: A stream-like object, or ``None``.

    Returns:
        ``True`` only when the stream reports an interactive terminal.
    """
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (OSError, ValueError):
        return False


def stdin_is_tty() -> bool:
    """Return whether stdin is attached to an interactive terminal."""
    return stream_is_tty(sys.stdin)


def stdout_is_tty() -> bool:
    """Return whether stdout is attached to an interactive terminal."""
    return stream_is_tty(sys.stdout)


def stderr_is_tty() -> bool:
    """Return whether stderr is attached to an interactive terminal."""
    return stream_is_tty(sys.stderr)
