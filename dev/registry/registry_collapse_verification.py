"""CLI entry point for the registry-wide collapse verification."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .registry_collapse_run import run_registry_verification


def main(argv: Sequence[str] | None = None) -> int:
    """Run the non-applying verifier and fail while any rollout result is incomplete."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument(
        "--authority-root",
        type=Path,
        default=None,
        help="published authority to prove unmutated (default: the working tree's publication)",
    )
    parser.add_argument(
        "--modelo",
        action="append",
        default=[],
        help="verify only this modelo identity; repeatable (default: every discovered modelo)",
    )
    arguments = parser.parse_args(argv)
    try:
        summary = run_registry_verification(
            registry_root=arguments.registry_root,
            source_root=arguments.source_root,
            work_dir=arguments.work_dir,
            authority_root=arguments.authority_root,
            modelos=tuple(arguments.modelo),
        )
    except Exception as exc:
        sys.stderr.write(f"registry collapse verification refused: {type(exc).__name__}: {exc}\n")
        return 1
    sys.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n")
    return 0 if summary["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
