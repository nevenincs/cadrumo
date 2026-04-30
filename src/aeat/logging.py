"""Internal module-level shim for `aeat.logging`.

Canonical location: :mod:`aeat.core.logging` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from .core.logging import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.logging"), "__all__", ())
