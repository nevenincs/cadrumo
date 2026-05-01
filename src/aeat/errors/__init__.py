"""Public-surface re-export shim for the errors package.

Canonical location moved to :mod:`aeat.core.errors` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import warnings as _warnings

from ..core.errors import *  # noqa: F403
from ..core.errors import __all__  # noqa: F401

_warnings.warn(
    "Importing from `aeat.errors` is deprecated; use `aeat.core.errors` instead.",
    DeprecationWarning,
    stacklevel=2,
)
