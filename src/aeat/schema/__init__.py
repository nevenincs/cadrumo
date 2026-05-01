"""Internal re-export shim for `aeat.schema`.

Canonical location: :mod:`aeat.domain.schema` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..domain.schema import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.domain.schema"), "__all__", ())
