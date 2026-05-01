"""Internal re-export shim for `aeat.sanitizer`.

Canonical location: :mod:`aeat.adapters.inbound.sanitizer` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.inbound.sanitizer import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.inbound.sanitizer"), "__all__", ())
