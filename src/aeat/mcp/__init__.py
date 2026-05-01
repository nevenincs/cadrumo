"""Internal re-export shim for `aeat.mcp`.

Canonical location: :mod:`aeat.entrypoints.mcp` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..entrypoints.mcp import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.entrypoints.mcp"), "__all__", ())
