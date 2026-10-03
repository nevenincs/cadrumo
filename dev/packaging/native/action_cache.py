"""Content-based reuse of shared CMake inputs across build configurations."""

from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


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
        return bool(state["inputs"] == identity) and all(
            (destination / name).is_file() and (destination / name).stat().st_size == size
            for name, size in state["outputs"].items()
        )
    except (ValueError, KeyError, OSError):
        return False


def completed(destination: Path, identity: str) -> None:
    """Publish a completion marker only after all shared outputs exist."""
    outputs = {
        p.relative_to(destination).as_posix(): p.stat().st_size
        for p in destination.rglob("*")
        if p.is_file() and p.name != "ready" and "__pycache__" not in p.parts
    }
    (destination / "ready").write_text(json.dumps({"inputs": identity, "outputs": outputs}), encoding="utf-8")
