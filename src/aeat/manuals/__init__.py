"""Internal re-export shim for `aeat.manuals`.

Canonical location: :mod:`aeat.domain.manuals` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.manuals import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.manuals"), "__all__", ())
