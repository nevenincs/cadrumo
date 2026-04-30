"""Public-surface re-export shim for the formulas package.

Canonical location moved to :mod:`aeat.domain.formulas` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import warnings as _warnings

from ..domain.formulas import *  # noqa: F403
from ..domain.formulas import __all__  # noqa: F401

_warnings.warn(
    "Importing from `aeat.formulas` is deprecated; use `aeat.domain.formulas` instead.",
    DeprecationWarning,
    stacklevel=2,
)
