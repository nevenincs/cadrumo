"""Real-behavior tests for the shipped-data source preflight."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from .._smoke_common import find_repo_root, tracked_source_data_paths
from ..source_preflight import _root_for, _summary

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TRACKED_DATA_ROOT = "src/cadrumo/_data"
_OUTSIDE_ROOTS = "<outside-tracked-data-roots>"

#: Below this the tracked-data walk has stopped seeing the shipped corpus.
#: This count is the DENOMINATOR the preflight declares ok over, so `> 0`
#: caught only a total collapse while a narrowed root or a tightened git
#: filter would leave it reporting success over a fraction. Live: 22,598
#: files, all under src/cadrumo/_data. A floor, not a pinned count.
_MINIMUM_TRACKED_DATA_FILES = 15000


def test_summary_counts_the_real_tracked_data_tree() -> None:
    """The summary reflects the live git-tracked shipped-data set, fully partitioned."""
    paths = tracked_source_data_paths(find_repo_root())
    summary = _summary(paths)

    assert summary["ok"] is True
    assert summary["tracked_file_count"] == len(paths)
    assert summary["tracked_file_count"] > _MINIMUM_TRACKED_DATA_FILES, summary["tracked_file_count"]
    # Every tracked path is partitioned under exactly one configured root, so the
    # per-root counts must sum back to the total with no path stranded outside.
    assert sum(summary["roots"].values()) == summary["tracked_file_count"]
    assert set(summary["roots"]) == {_TRACKED_DATA_ROOT}


def test_root_for_classifies_tracked_paths_and_the_outside_sentinel() -> None:
    """A path under a configured root resolves to it; anything else is the sentinel."""
    assert _root_for(f"{_TRACKED_DATA_ROOT}/registry/aeat/modelos/036/manifest.toml") == _TRACKED_DATA_ROOT
    assert _root_for(_TRACKED_DATA_ROOT) == _TRACKED_DATA_ROOT
    assert _root_for("README.md") == _OUTSIDE_ROOTS
    assert _root_for("src/cadrumo/core/config.py") == _OUTSIDE_ROOTS


def test_source_preflight_cli_json_contract() -> None:
    """The module CLI must emit a stable machine-readable success summary."""
    result = subprocess.run(
        [sys.executable, "-m", "dev.packaging.source_preflight", "--json"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["tracked_file_count"] > _MINIMUM_TRACKED_DATA_FILES, payload["tracked_file_count"]
    assert sum(payload["roots"].values()) == payload["tracked_file_count"]
    assert set(payload["roots"]) == {_TRACKED_DATA_ROOT}


def test_source_preflight_cli_human_output_reports_counts_and_repository() -> None:
    """The default human surface prints the total, per-root counts, and the repository path."""
    result = subprocess.run(
        [sys.executable, "-m", "dev.packaging.source_preflight"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "tracked shipped-data files present:" in result.stdout
    assert _TRACKED_DATA_ROOT in result.stdout
    assert "repository\t" in result.stdout
