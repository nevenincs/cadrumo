"""Public-surface re-export shim for the submission package.

Canonical location moved to :mod:`aeat.adapters.outbound.aeat.export` per the
aeat-restructure ADR (Public surface and semver).
"""

from __future__ import annotations

import warnings as _warnings

from ..adapters.outbound.aeat.export import *  # noqa: F403
from ..adapters.outbound.aeat.export import __all__  # noqa: F401

_warnings.warn(
    "Importing from `aeat.submission` is deprecated; use `aeat.adapters.outbound.aeat.export` instead.",
    DeprecationWarning,
    stacklevel=2,
)
