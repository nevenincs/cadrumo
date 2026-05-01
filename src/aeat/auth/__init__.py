"""Public-surface re-export shim for the auth package.

Canonical location moved to :mod:`aeat.adapters.outbound.aeat.auth` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import warnings as _warnings

from ..adapters.outbound.aeat.auth import *  # noqa: F403
from ..adapters.outbound.aeat.auth import __all__  # noqa: F401

_warnings.warn(
    "Importing from `aeat.auth` is deprecated; use `aeat.adapters.outbound.aeat.auth` instead.",
    DeprecationWarning,
    stacklevel=2,
)
