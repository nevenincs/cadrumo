"""Canonical paths for date-partitioned development run evidence."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def allocate_run_directory(
    repository: Path,
    *,
    family: str,
    label: str,
    now: datetime | None = None,
) -> Path:
    """Return a collision-resistant run path below the repository's ``.logs``."""
    started = now or datetime.now(tz=UTC)
    marker = f"{started:%Y%m%dT%H%M%S.%fZ}-{label}-{os.getpid()}-{uuid4().hex[:8]}"
    return repository / ".logs" / family / f"{started:%Y-%m-%d}" / marker
