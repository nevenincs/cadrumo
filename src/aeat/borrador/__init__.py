"""Internal re-export shim for `aeat.borrador`.

Canonical location: :mod:`aeat.adapters.inbound.borrador` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.inbound.borrador import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.inbound.borrador"), "__all__", ())
