"""The routing posture one command-graph node declares toward the full-screen frontend.

A command declares whether the full-screen frontend has a destination for it.
Both entrypoints need that declaration and for opposite reasons: the command
line reads it to refuse a request it cannot route, and the full-screen frontend
reads it to know which commands it is expected to present.

The declaration used to live inside the command-line package, which put it out
of the frontend's reach. A sibling entrypoint may not import the other -- an
import contract holds that prohibition, because a frontend importing the
command line would pull that package's initialiser, and with it Typer, into a
process that has no command line. So the posture was declared where only one of
its two readers could see it.

This module is the fix, and it takes the shape the out-of-process session
protocol beside it already established: it sits next to both entrypoint
packages rather than inside either, so the posture has exactly one definition
and neither package has to import the other to agree with it. A copy per side
would agree only until someone edited one of them.

The posture is transport-adjacent rather than policy. It says where a command
may be presented, not whether the operator may run it, what it costs, or
whether its preconditions hold -- those are the application layer's, and a
value here must never be read as answering them.

See Also:
    :mod:`full_screen_session_protocol`
        The sibling crossing that carries a subject between the two
        entrypoints, owned by neither for the same reason.
"""

from __future__ import annotations

from enum import Enum

__all__: tuple[str, ...] = ("TuiCapability",)


class TuiCapability(Enum):
    """Closed TUI routing posture for one command-graph node."""

    NOT_IMPLEMENTED = "not-implemented"
    AVAILABLE = "available"
