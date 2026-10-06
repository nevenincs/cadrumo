"""Content-based reuse of shared CMake inputs across build configurations."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .build_toolchain import sysroot_inventory


@contextmanager
def action_lock(build: Path, action: str) -> Iterator[None]:
    """Serialize shared writers; OS locks release even if the build is interrupted."""
    with (build / f".{action}.lock").open("a+b") as stream:
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except PermissionError:
                    time.sleep(0.2)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def fingerprint(inputs: Path, extra: tuple[Path, ...] = ()) -> str:
    """Hash the enrolled inputs by name and bytes, including selected authority."""
    result = hashlib.sha256()
    paths = {*map(Path, inputs.read_text(encoding="utf-8").splitlines()), *extra}
    for path in sorted(paths):
        result.update(str(path.resolve()).encode("utf-8"))
        try:
            with path.open("rb") as source:
                result.update(hashlib.file_digest(source, "sha256").digest())
        except OSError as error:
            raise OSError(f"Cannot fingerprint build input: {path}") from error
    return result.hexdigest()


def current(destination: Path, identity: str) -> bool:
    """Reuse only complete outputs from exactly these inputs."""
    marker = destination / "ready"
    if not marker.is_file():
        return False
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
        return bool(
            state["schema"] == 3 and state["inputs"] == identity and state["outputs"] == _inventory(destination)
        )
    except (ValueError, KeyError, TypeError, OSError):
        return False


def _inventory(destination: Path) -> dict[str, Any]:
    marker = destination / "ready"
    if destination.is_symlink() or destination.is_junction() or marker.is_symlink() or marker.is_junction():
        raise ValueError("Build cache root and completion marker must not be linked")
    inventory = sysroot_inventory(destination, excluded=frozenset({"ready"}))
    return {"files": inventory["files"], "links": inventory["links"]}


def completed(destination: Path, identity: str) -> None:
    """Publish a completion marker binding the complete output inventory to its bytes."""
    state = {"schema": 3, "inputs": identity, "outputs": _inventory(destination)}
    (destination / "ready").write_text(json.dumps(state), encoding="utf-8")
