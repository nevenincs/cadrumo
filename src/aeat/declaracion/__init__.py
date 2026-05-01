"""Internal re-export shim for `aeat.declaracion`.

Canonical location: :mod:`aeat.adapters.inbound.declaracion` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.inbound.declaracion import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.inbound.declaracion"), "__all__", ())
