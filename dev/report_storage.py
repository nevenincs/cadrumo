"""Optional CI artifact paths under the canonical Cadrumo storage authority."""

from __future__ import annotations

import os
from pathlib import Path

from cadrumo.core.storage_environment import resolve_storage_path


def report_directory(destination: str | Path | None = None) -> Path | None:
    """Resolve an explicit destination or the refined and legacy report controls."""
    if destination is None:
        raw = os.environ.get("CADRUMO_CI_REPORTS_DIR", "").strip() or os.environ.get("VAULTSPEC_CI_REPORTS", "").strip()
    else:
        raw = str(destination).strip()
    return resolve_storage_path(raw) if raw else None
