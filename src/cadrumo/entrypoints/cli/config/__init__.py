"""Inert namespace for the demand-loaded configuration command surface.

This package exports nothing.  The composed ``config`` subtree and its command
graph are defined in ``_command_tree``; the command specs live in
``_command_specs`` and the individual verb modules beside them.  Callers import
from the defining module, never from this namespace.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
