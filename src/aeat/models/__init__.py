"""Internal re-export shim for `aeat.models`.

Canonical location: :mod:`aeat.domain.modelos` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.modelos import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.modelos"), "__all__", ())
