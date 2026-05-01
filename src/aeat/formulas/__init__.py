"""Public-surface re-export shim for the formulas package.

Canonical location moved to :mod:`aeat.domain.formulas` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import importlib as _importlib
import warnings as _warnings

from ..domain.formulas import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.formulas"), "__all__", ())

_warnings.warn(
    "Importing from `aeat.formulas` is deprecated; use `aeat.domain.formulas` instead.",
    DeprecationWarning,
    stacklevel=2,
)
