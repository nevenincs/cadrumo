"""Internal module-level shim for `aeat._paths`.

Canonical location: :mod:`aeat.core.paths` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from .core.paths import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.paths"), "__all__", ())
