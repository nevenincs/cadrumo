"""Internal re-export shim for `aeat.portals`.

Canonical location: :mod:`aeat.domain.portals` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.portals import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.portals"), "__all__", ())
