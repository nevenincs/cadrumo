"""Refresh only CMake-owned installation staging after validating its previous receipt."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from .build_paths import build_paths
from .hashing import digest
from .installation import member, prepare, verify_inventory


def refresh(payload: Path, identity: Path, build: Path, desktop: str | None = None) -> None:
    """Construct the next stage before replacing a verified, generated previous stage."""
    paths = build_paths(build)
    stage = paths["installation_stage"]
    metadata = paths["installation_metadata"]
    receipt = member(metadata, "installation.json")
    if stage.exists():
        verify_inventory(stage, receipt)
    work = paths["installation_work"]
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temporary:
        candidate = Path(temporary)
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
        prepare(payload, identity, candidate, desktop)
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
            shutil.rmtree(stage)
        if metadata.exists():
            shutil.rmtree(metadata)
        stage.parent.mkdir(parents=True, exist_ok=True)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        (candidate / "stage").replace(stage)
        (candidate / "metadata").replace(metadata)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--desktop")
    arguments = parser.parse_args()
    refresh(arguments.payload, arguments.identity, arguments.build, arguments.desktop)
