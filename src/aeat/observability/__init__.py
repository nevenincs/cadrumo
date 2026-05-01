"""Internal re-export shim for `aeat.observability`.

Canonical location: :mod:`aeat.core.observability` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..core.observability import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.observability"), "__all__", ())
