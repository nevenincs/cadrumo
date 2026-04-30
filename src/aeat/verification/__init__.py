"""Internal re-export shim for `aeat.verification`.

Canonical location: :mod:`aeat.application.verification` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..application.verification import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.application.verification"), "__all__", ())
