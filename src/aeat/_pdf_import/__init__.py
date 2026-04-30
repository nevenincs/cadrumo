"""Internal re-export shim for `aeat._pdf_import`.

Canonical location: :mod:`aeat.adapters.inbound.pdf` post the aeat-restructure layout move.
"""

from __future__ import annotations

import importlib as _importlib

from ..adapters.inbound.pdf import *  # noqa: F403

__all__ = getattr(_importlib.import_module("aeat.adapters.inbound.pdf"), "__all__", ())
