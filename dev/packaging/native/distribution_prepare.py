"""Refresh only CMake-owned installation staging after validating its previous receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .action_cache import action_lock
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest
from .installation import member, prepare, verify_inventory
from .installation_currency import existing
from .installation_reuse import InstallationReuse, public_directory, publish


def refresh(payload: Path, identity: Path, build: Path, desktop: str | None = None) -> None:
    """Serialize candidate staging and publication across CLI and CMake callers."""
    with action_lock(build, "installation-staging"):
        _refresh(payload, identity, build, desktop)


def _refresh(payload: Path, identity: Path, build: Path, desktop: str | None = None) -> None:
    """Construct the next stage before replacing a verified, generated previous stage."""
    paths = build_paths(build)
    stage = paths["installation_stage"]
    metadata = paths["installation_metadata"]
    receipt = member(metadata, "installation.json")
    if stage.exists():
        from . import installation

        if existing(payload, identity, stage, metadata, desktop, installation.REPO_ROOT, allow_change=True):
            return
    work = paths["installation_work"]
    work.mkdir(parents=True, exist_ok=True)
    with public_directory(work, "candidate-") as candidate:
        (candidate / "build-paths.json").write_text(
            json.dumps(
                {
                    "paths": {
                        "installation_stage": "stage",
                        "installation_metadata": "metadata",
                        "installation_work": "work",
                    }
                }
            ),
            encoding="utf-8",
        )
        reuse = None
        if stage.exists():
            previous = json.loads(receipt.read_text(encoding="utf-8"))
            # Old private temporary stages migrate by copying once; never carry
            # their retained Windows DACL into a new public output via hardlinks.
            if previous.get("staging_generation") == 1:
                reuse = InstallationReuse(stage, candidate / "stage", previous["files"])
        prepare(payload, identity, candidate, desktop, copy_file=reuse.copy if reuse else None)
        # Receipts outlive generated staging, including an explicit target clean.
        receipts = paths["installation_receipts"]
        receipts.mkdir(parents=True, exist_ok=True)
        retained_sources = [candidate / "metadata/installation.json"]
        if stage.exists():
            retained_sources.append(receipt)
        for owned in retained_sources:
            retained = member(receipts, f"{digest(owned)}.json")
            if retained.exists() and retained.read_bytes() != owned.read_bytes():
                raise ValueError("Retained installation receipt differs from its content identity")
            if not retained.exists():
                retained.write_bytes(owned.read_bytes())
        if stage.exists():
            verify_inventory(stage, receipt)
        publish(stage, metadata, candidate)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--desktop")
    arguments = parser.parse_args()
    refresh(arguments.payload, arguments.identity, arguments.build, arguments.desktop)
