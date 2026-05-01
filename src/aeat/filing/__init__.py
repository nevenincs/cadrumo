"""Internal re-export shim for `aeat.filing`.

Canonical location: :mod:`aeat.application.filing` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..application.filing import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.application.filing"), "__all__", ())
