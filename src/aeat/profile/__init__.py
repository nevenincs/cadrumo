"""Internal re-export shim for `aeat.profile`.

Canonical location: :mod:`aeat.domain.profile` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.profile import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.profile"), "__all__", ())
