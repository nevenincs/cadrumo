"""Internal re-export shim for `aeat.storage`.

Canonical location: :mod:`aeat.adapters.persistence.storage` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.persistence.storage import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.persistence.storage"), "__all__", ())
