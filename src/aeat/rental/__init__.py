"""Internal re-export shim for `aeat.rental`.

Canonical location: :mod:`aeat.domain.rental` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.rental import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.rental"), "__all__", ())
