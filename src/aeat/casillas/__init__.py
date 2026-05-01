"""Internal re-export shim for `aeat.casillas`.

Canonical location: :mod:`aeat.domain.casillas` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.casillas import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.casillas"), "__all__", ())
