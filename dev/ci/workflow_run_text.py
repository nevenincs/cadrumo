"""Read the shell a workflow step or justfile recipe actually executes.

A `run:` block is not a script the reader may treat as one long string. It is a
script with comments in it, and a comment is prose: the shell parses it and
does nothing. Every gate that asks "does this lane invoke X" by testing
`"X" in run` therefore answers yes for a lane where the only mention of X sits
behind a `#` -- an invocation that was commented out, a recipe named in an
explanatory note, a target listed in a rationale paragraph above the command.
The gate stays green, and nothing runs.

That is not hypothetical here. A commented-out module invocation and a marker
named only in a comment each satisfied a substring gate in this tree while the
thing they named could not execute. The fix in both cases was the same, and it
is the whole content of this module: read the EXECUTED lines, and judge those.

The comment rule is the shell own and deliberately no wider than it. A line
whose first non-blank character is `#` is a comment; a `#` anywhere else may be
a fragment identifier, a colour, or a quoted literal, and stripping from there
would silently truncate real commands.
"""

from __future__ import annotations

from collections.abc import Iterable

__all__ = ["executed_lines", "executed_text"]


def executed_lines(script: object) -> tuple[str, ...]:
    """Return the stripped lines of ``script`` the shell would execute.

    Blank lines and whole-line comments are dropped; every other line is
    returned with surrounding whitespace removed, in source order.

    ``script`` is accepted as :class:`object` because a step ``run`` is
    whatever YAML produced -- absent, a string, or a scalar of another type --
    and a gate that raised on the absent case would fail on the very steps it
    has nothing to say about.
    """
    lines: list[str] = []
    for raw_line in str(script or "").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            lines.append(line)
    return tuple(lines)


def executed_text(scripts: object | Iterable[object]) -> str:
    """Return one newline-joined surface of everything ``scripts`` executes.

    Accepts a single script or an iterable of them, so a caller joining every
    step in a job gets the same comment discipline as one reading a single
    step. A bare string is one script, never an iterable of characters.
    """
    if isinstance(scripts, str) or not isinstance(scripts, Iterable):
        return "\n".join(executed_lines(scripts))
    return "\n".join(line for script in scripts for line in executed_lines(script))
