"""Internal re-export shim for `aeat.sync`.

Canonical location: :mod:`aeat.application.sync` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..application.sync import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.application.sync"), "__all__", ())
