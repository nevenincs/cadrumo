"""Internal re-export shim for `aeat.cli`.

Canonical location: :mod:`aeat.entrypoints.cli` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..entrypoints.cli import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.entrypoints.cli"), "__all__", ())
