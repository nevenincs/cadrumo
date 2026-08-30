"""Retention pruning for wallet diagnostic dump files.

The IVA-compensation-wallet read writes redacted ``<label>-summary.txt`` dump
files into the opt-in ``cadrumo_wallet_diagnostic_dump_dir`` when configured.
``prune_wallet_diagnostic_dumps`` gives that opt-in directory a declared
retention lifecycle: dump files older than ``cadrumo_wallet_diagnostic_retention_days``
are removed. Ages are set with ``os.utime`` on real files (plain files, no
bucket session) and the prune runs under the real clock.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ......core.config import override_settings
from ..iva_compensation_wallet import prune_wallet_diagnostic_dumps

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _dump_file(dump_dir: Path, name: str, *, age_days: int, anchor: datetime) -> Path:
    path = dump_dir / name
    path.write_text("label=probe\n", encoding="utf-8")
    stamp = (anchor - timedelta(days=age_days)).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_prune_removes_dump_files_older_than_retention_window(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    fresh = _dump_file(tmp_path, "final-parse-input-summary.txt", age_days=1, anchor=anchor)
    stale = _dump_file(tmp_path, "pre-execute-summary.txt", age_days=45, anchor=anchor)

    removed = prune_wallet_diagnostic_dumps(tmp_path, retention_days=30)

    assert removed == 1
    assert fresh.exists()
    assert not stale.exists()


def test_prune_keeps_files_inside_the_window(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    a = _dump_file(tmp_path, "post-own-name-summary.txt", age_days=1, anchor=anchor)
    b = _dump_file(tmp_path, "post-execute-summary.txt", age_days=5, anchor=anchor)

    removed = prune_wallet_diagnostic_dumps(tmp_path, retention_days=30)

    assert removed == 0
    assert a.exists()
    assert b.exists()


def test_prune_missing_dump_directory_is_a_noop(tmp_path: Path) -> None:
    assert prune_wallet_diagnostic_dumps(tmp_path / "does-not-exist", retention_days=30) == 0


def test_prune_defaults_to_central_retention_setting(tmp_path: Path) -> None:
    anchor = datetime.now(UTC)
    _dump_file(tmp_path, "final-parse-input-summary.txt", age_days=1, anchor=anchor)
    _dump_file(tmp_path, "pre-execute-summary.txt", age_days=400, anchor=anchor)

    with override_settings(cadrumo_wallet_diagnostic_retention_days=30):
        removed = prune_wallet_diagnostic_dumps(tmp_path)

    assert removed == 1
    assert (tmp_path / "final-parse-input-summary.txt").exists()
    assert not (tmp_path / "pre-execute-summary.txt").exists()
