"""Internal re-export shim for `aeat.financial`.

Canonical location: :mod:`aeat.domain.financial` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.financial import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.financial"), "__all__", ())
