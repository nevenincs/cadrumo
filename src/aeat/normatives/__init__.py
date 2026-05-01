"""Internal re-export shim for `aeat.normatives`.

Canonical location: :mod:`aeat.domain.normatives` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.normatives import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.normatives"), "__all__", ())
