"""Pure recognition of CLI metadata invocations.

Help and version surfaces must remain available even when operator state cannot
be opened. This import-light predicate is shared by CLI startup, output, and
logging so each boundary agrees on exactly which invocation tokens have that
metadata-only posture.
"""

from __future__ import annotations

from collections.abc import Sequence

_METADATA_ARGUMENTS = frozenset({"--help", "-h", "--version", "-V"})


def is_metadata_invocation(arguments: Sequence[str]) -> bool:
    """Return whether ``arguments`` request help or version metadata."""
    return any(argument in _METADATA_ARGUMENTS for argument in arguments)


__all__ = ["is_metadata_invocation"]
