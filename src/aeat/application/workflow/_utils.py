"""Shared utilities for the workflow application layer."""

from __future__ import annotations

from ...core.time import now as utc_now
from ...domain.contribuyente import normalise_key

__all__ = ["normalise_key", "utc_now"]
