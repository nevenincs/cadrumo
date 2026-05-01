"""Internal re-export shim for `aeat.review`.

Canonical location: :mod:`aeat.application.review` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..application.review import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.application.review"), "__all__", ())
