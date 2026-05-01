"""Internal re-export shim for `aeat.testing`.

Canonical location: :mod:`aeat.domain.testing` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.testing import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.testing"), "__all__", ())
