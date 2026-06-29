"""Validate that every git-tracked shipped data file exists on disk."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import TypedDict

from .smoke_core import _TRACKED_DATA_ROOTS, _repo_root, _tracked_source_data_paths


class SourceDataSummary(TypedDict):
    """Machine-readable shipped-data preflight summary."""

    ok: bool
    tracked_file_count: int
    roots: dict[str, int]


def _root_for(path: str) -> str:
    """Return the configured tracked data root that owns ``path``."""
    for root in _TRACKED_DATA_ROOTS:
        if path.startswith(f"{root}/") or path == root:
            return root
    return "<outside-tracked-data-roots>"


def _summary(paths: set[str]) -> SourceDataSummary:
    """Build a stable source-data summary for humans and automation."""
    counts = Counter(_root_for(path) for path in paths)
    return {
        "ok": True,
        "tracked_file_count": len(paths),
        "roots": dict(sorted(counts.items())),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the shipped-data source preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable summary.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    paths = _tracked_source_data_paths(repo_root)
    summary = _summary(paths)
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print(f"tracked shipped-data files present: {summary['tracked_file_count']}")
    for root, count in summary["roots"].items():
        print(f"{root}\t{count}")
    print(f"repository\t{Path(repo_root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
