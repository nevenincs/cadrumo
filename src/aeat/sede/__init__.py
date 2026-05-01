"""Internal re-export shim for `aeat.sede`.

Canonical location: :mod:`aeat.adapters.outbound.aeat.sede` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.outbound.aeat.sede import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.outbound.aeat.sede"), "__all__", ())
