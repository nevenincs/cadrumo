"""Internal re-export shim for `aeat.setup`.

Canonical location: :mod:`aeat.application.setup` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..application.setup import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.application.setup"), "__all__", ())
