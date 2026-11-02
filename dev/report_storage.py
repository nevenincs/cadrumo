"""Optional CI artifact paths under the canonical Cadrumo storage authority."""

from __future__ import annotations

import os
from pathlib import Path

from cadrumo.core.storage_environment import resolve_storage_path


def report_directory(destination: str | Path | None = None) -> Path | None:
    """Resolve an explicit destination or the ``CADRUMO_CI_REPORTS_DIR`` control."""
    raw = os.environ.get("CADRUMO_CI_REPORTS_DIR", "") if destination is None else str(destination)
    raw = raw.strip()
    return resolve_storage_path(raw) if raw else None
