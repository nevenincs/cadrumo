"""Shared utilities for the workflow application layer."""

from __future__ import annotations

from ...core._time import utc_now
from ...domain.profile import normalise_key

__all__ = ["normalise_key", "utc_now"]
