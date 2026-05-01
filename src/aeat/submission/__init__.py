"""Public-surface re-export shim for the submission package.

Canonical location moved to :mod:`aeat.adapters.outbound.aeat.export` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import importlib as _importlib
import warnings as _warnings

from ..adapters.outbound.aeat.export import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.outbound.aeat.export"), "__all__", ())

_warnings.warn(
    "Importing from `aeat.submission` is deprecated; use `aeat.adapters.outbound.aeat.export` instead.",
    DeprecationWarning,
    stacklevel=2,
)
