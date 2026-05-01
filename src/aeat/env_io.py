"""Internal module-level shim for `aeat.env_io`.

Canonical location: :mod:`aeat.core.env_io` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from .core.env_io import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.env_io"), "__all__", ())
