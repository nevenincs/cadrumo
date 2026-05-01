"""Internal re-export shim for `aeat.browser`.

Canonical location: :mod:`aeat.adapters.outbound.aeat.browser` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.outbound.aeat.browser import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.outbound.aeat.browser"), "__all__", ())
