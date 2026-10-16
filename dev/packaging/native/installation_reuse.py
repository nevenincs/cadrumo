"""Reuse verified immutable installation members while constructing a private candidate."""

from __future__ import annotations

import os
import shutil
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .hashing import digest
from .installation import member


@contextmanager
def public_directory(parent: Path, prefix: str) -> Generator[Path]:
    """Let generated public outputs inherit their actual build parent's permissions."""
    directory = parent / f"{prefix}{uuid4().hex}"
    directory.mkdir(mode=0o755)
    try:
        yield directory
    finally:
        if directory.exists():
            shutil.rmtree(directory)


class InstallationReuse:
    """Link only bytes still matching the previous installation owner's inventory."""

    def __init__(self, previous: Path, candidate: Path, files: dict[str, str]) -> None:
        """Bind immutable reuse to one admitted previous stage and private candidate."""
        self.previous = previous
        self.candidate = candidate
        self.files = files

    def copy(self, source: str | Path, destination: str | Path) -> str | Path:
        """Copy changed bytes, otherwise link the previous unchanged owned member."""
        original, output = Path(source), Path(destination)
        relative = output.relative_to(self.candidate).as_posix()
        checksum = self.files.get(relative)
        previous = member(self.previous, relative)
        if (
            checksum is not None
            and digest(original) == checksum
            and digest(previous) == checksum
            and original.stat().st_mode == previous.stat().st_mode
        ):
            try:
                os.link(previous, output)
                return destination
            except OSError:
                # Cross-volume or unsupported links still preserve correctness;
                # the caller owns a fresh private destination for this copy.
                pass
        return shutil.copy2(source, destination)


def publish(stage: Path, metadata: Path, candidate: Path) -> None:
    """Retain previous stage and metadata until both candidate renames succeed."""
    # A failed rollback must survive the candidate's TemporaryDirectory cleanup.
    backup = candidate.parent / f"previous-{uuid4().hex}"
    backup.mkdir()
    previous_stage = backup / "stage"
    previous_metadata = backup / "metadata"
    stage_promoted = metadata_promoted = False
    try:
        if stage.exists():
            stage.replace(previous_stage)
        if metadata.exists():
            metadata.replace(previous_metadata)
        stage.parent.mkdir(parents=True, exist_ok=True)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        (candidate / "stage").replace(stage)
        stage_promoted = True
        (candidate / "metadata").replace(metadata)
        metadata_promoted = True
    except BaseException:
        if metadata_promoted:
            metadata.replace(candidate / "metadata")
        if stage_promoted:
            stage.replace(candidate / "stage")
        if previous_metadata.exists():
            previous_metadata.replace(metadata)
        if previous_stage.exists():
            previous_stage.replace(stage)
        backup.rmdir()
        raise
    shutil.rmtree(backup)
