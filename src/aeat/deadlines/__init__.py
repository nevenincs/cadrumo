"""Internal re-export shim for `aeat.deadlines`.

Canonical location: :mod:`aeat.domain.deadlines` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.deadlines import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.deadlines"), "__all__", ())
