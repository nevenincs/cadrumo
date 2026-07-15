"""Checkpoint packaging-smoke manifests without retaining ephemeral runtimes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Final

_MANIFEST_NAME: Final[str] = "packaging-smoke-manifest.json"


def checkpoint_smoke_evidence(
    smoke_root: Path,
    evidence_root: Path,
    *,
    prune_completed: bool,
) -> tuple[Path, ...]:
    """Copy direct-child manifests and optionally remove their completed work dirs.

    Looking up only the known manifest leaf avoids recursively traversing secure
    runtime directories created by container probes. A work directory is pruned
    only after its manifest has been validated and atomically checkpointed, so failed or
    incomplete runs remain available for diagnosis.
    """
    if not smoke_root.is_dir():
        return ()

    evidence_root.mkdir(parents=True, exist_ok=True)
    checkpointed: list[Path] = []
    for work_dir in sorted(path for path in smoke_root.iterdir() if path.is_dir()):
        manifest = work_dir / _MANIFEST_NAME
        if not manifest.is_file():
            continue
        payload = manifest.read_bytes()
        document = json.loads(payload)
        if not isinstance(document, dict) or document.get("ok") is not True:
            raise ValueError(f"packaging smoke manifest is not successful: {manifest}")

        target = evidence_root / f"{work_dir.name}.json"
        temporary = target.with_suffix(".json.tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        checkpointed.append(target)
        if prune_completed:
            shutil.rmtree(work_dir)

    return tuple(checkpointed)


def main(argv: list[str] | None = None) -> int:
    """Checkpoint packaging-smoke evidence for CI artifact retention."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--prune-completed",
        action="store_true",
        help="Remove only work directories whose successful manifest was checkpointed.",
    )
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    smoke_root = repo_root / "var" / "packaging-smoke"
    evidence_root = repo_root / "var" / "packaging-smoke-evidence"
    checkpointed = checkpoint_smoke_evidence(
        smoke_root,
        evidence_root,
        prune_completed=args.prune_completed,
    )
    print(f"checkpointed packaging smoke manifests: {len(checkpointed)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
