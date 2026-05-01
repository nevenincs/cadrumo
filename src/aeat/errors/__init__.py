"""Public-surface re-export shim for the errors package.

Canonical location moved to :mod:`aeat.core.errors` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import importlib as _importlib
import warnings as _warnings

from ..core.errors import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.core.errors"), "__all__", ())

_warnings.warn(
    "Importing from `aeat.errors` is deprecated; use `aeat.core.errors` instead.",
    DeprecationWarning,
    stacklevel=2,
)
