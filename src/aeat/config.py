"""Internal module-level shim for `aeat.config`.

Canonical location: :mod:`aeat.core.config` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from .core.config import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.config"), "__all__", ())
