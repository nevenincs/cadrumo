from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ..paths import allocate_run_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_run_directory_is_date_partitioned_unique_and_repository_local(tmp_path: Path) -> None:
    instant = datetime(2026, 9, 8, 12, 34, 56, 123456, tzinfo=UTC)

    first = allocate_run_directory(tmp_path, family="audit-runs", label="audit-all", now=instant)
    second = allocate_run_directory(tmp_path, family="audit-runs", label="audit-all", now=instant)

    assert first.parent == tmp_path / ".logs" / "audit-runs" / "2026-09-08"
    assert first.name.startswith("20260908T123456.123456Z-audit-all-")
    assert first != second
