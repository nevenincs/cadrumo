"""Internal re-export shim for `aeat.identity`.

Canonical location: :mod:`aeat.adapters.inbound.identity` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.inbound.identity import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.inbound.identity"), "__all__", ())
