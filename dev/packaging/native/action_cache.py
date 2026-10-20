"""Content-based reuse of shared CMake inputs across build configurations."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import time
from collections.abc import Generator, Iterable
from contextlib import contextmanager, nullcontext
from pathlib import Path
from typing import Any

from .build_timing import BuildTimings
from .build_toolchain import sysroot_inventory
from .hashing import digest


@contextmanager
def action_lock(build: Path, action: str, *, timings: BuildTimings | None = None) -> Generator[None]:
    """Serialize shared writers; OS locks release even if the build is interrupted."""
    with (build / f".{action}.lock").open("a+b") as stream:
        stream.seek(0)
        with timings.phase("lock-wait") if timings is not None else nullcontext():
            if os.name == "nt":
                import msvcrt

                announced = False
                while True:
                    try:
                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except PermissionError:
                        if not announced and timings is not None:
                            timings.log.status(f"waiting for the {action} lock another build step holds")
                            announced = True
                        time.sleep(0.2)
            else:
                import fcntl

                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    if timings is not None:
                        timings.log.status(f"waiting for the {action} lock another build step holds")
                    fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _redirects(entry: os.DirEntry[str]) -> bool:
    """Whether a directory entry is a link, junction or other reparse point that resolution follows."""
    if entry.is_symlink() or entry.is_junction():
        return True
    attributes = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def resolve_paths(paths: Iterable[Path]) -> dict[Path, Path]:
    """Return ``{path: path.resolve()}``, resolving each parent directory once.

    A plain file is its resolved parent joined with its name as the directory lists it, which
    is what full resolution returns; a link, a missing file or an unreadable directory is
    resolved on its own.
    """
    by_parent: dict[Path, list[Path]] = {}
    for path in paths:
        by_parent.setdefault(path.parent, []).append(path)
    resolved: dict[Path, Path] = {}
    for parent, members in by_parent.items():
        real_parent = parent
        try:
            real_parent = parent.resolve(strict=True)
            with os.scandir(parent) as listing:
                entries = {os.path.normcase(entry.name): entry for entry in listing}
        except OSError:
            entries = {}
        for path in members:
            entry = entries.get(os.path.normcase(path.name))
            if entry is None or _redirects(entry):
                resolved[path] = path.resolve()
            else:
                resolved[path] = real_parent / entry.name
    return resolved


def fingerprint(inputs: Path, extra: tuple[Path, ...] = (), *, outside: Path | None = None) -> str:
    """Hash the enrolled inputs by name and bytes, including selected authority.

    Args:
        inputs: The file listing the enrolled inputs, one path per line.
        extra: Inputs enrolled by the caller rather than by the listing.
        outside: A directory whose own files are left out. A build
            configuration enrolls files of its own directory that say where
            that configuration writes; a fingerprint that is to mean the same
            thing in every configuration of one checkout cannot include them.
    """
    result = hashlib.sha256()
    paths = {*map(Path, inputs.read_text(encoding="utf-8").splitlines()), *extra}
    resolved = resolve_paths(paths)
    if outside is not None:
        boundary = outside.resolve()
        paths = {path for path in paths if not resolved[path].is_relative_to(boundary)}
    for path in sorted(paths):
        result.update(str(resolved[path]).encode("utf-8"))
        try:
            # Inside a digest cache an unchanged input is not read again; the bytes hashed are the same.
            result.update(bytes.fromhex(digest(path)))
        except OSError as error:
            raise OSError(f"Cannot fingerprint build input: {path}") from error
    return result.hexdigest()


def modified_inputs(inputs: Path, extra: tuple[Path, ...], since_ns: int) -> list[Path]:
    """Return the enrolled inputs changed, removed or replaced at or after ``since_ns``, in name order."""
    changed = []
    for path in sorted({*map(Path, inputs.read_text(encoding="utf-8").splitlines()), *extra}):
        try:
            metadata = path.stat()
        except OSError:
            changed.append(path)
            continue
        if max(metadata.st_mtime_ns, metadata.st_ctime_ns) >= since_ns:
            changed.append(path)
    return changed


def current(destination: Path, identity: str) -> bool:
    """Reuse only complete outputs from exactly these inputs."""
    return staleness(destination, identity) is None


def staleness(destination: Path, identity: str) -> str | None:
    """Say why ``destination`` cannot be reused for these inputs, or ``None`` when it can."""
    marker = destination / "ready"
    if not marker.is_file():
        return "no completion receipt"
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
        if state["schema"] != 3:
            return "completion receipt has an older schema"
        if state["inputs"] != identity:
            return "inputs changed"
        if state["outputs"] != _inventory(destination):
            return "outputs differ from the completion receipt"
    except (ValueError, KeyError, TypeError, OSError):
        return "completion receipt is unreadable"
    return None


def receipt_staleness(destination: Path, identity: str) -> str | None:
    """Say why the completion receipt of ``destination`` was not written for these inputs, or ``None``.

    Unlike :func:`staleness` this does not re-inventory the outputs; a caller pairs it with a
    settled build record whose staged artifacts it checks.
    """
    marker = destination / "ready"
    if destination.is_symlink() or destination.is_junction() or marker.is_symlink() or marker.is_junction():
        return "build cache root or completion marker is linked"
    try:
        state = json.loads(marker.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return "no completion receipt"
    except (ValueError, OSError):
        return "completion receipt is unreadable"
    if not isinstance(state, dict) or state.get("schema") != 3:
        return "completion receipt has an older schema"
    if state.get("inputs") != identity:
        return "inputs changed"
    return None


def _inventory(destination: Path) -> dict[str, Any]:
    marker = destination / "ready"
    if destination.is_symlink() or destination.is_junction() or marker.is_symlink() or marker.is_junction():
        raise ValueError("Build cache root and completion marker must not be linked")
    inventory = sysroot_inventory(destination, excluded=frozenset({"ready"}))
    return {"files": inventory["files"], "links": inventory["links"]}


_RECEIPT_PREFIX = json.dumps({"schema": 3})[:-1].encode("utf-8") + b","
"""How every completion receipt :func:`completed` writes begins."""


def receipt_owner(path: Path, build: Path) -> Path | None:
    """Return the producer destination inside ``build`` whose completion receipt covers ``path``.

    The receipt binds the destination's whole output inventory, so its bytes stand for every
    member of the destination while it exists; a producer removes it before rewriting anything.
    """
    root = build.resolve()
    candidate = path.resolve()
    while candidate != root and candidate.is_relative_to(root):
        marker = candidate / "ready"
        if marker.is_file() and not marker.is_symlink() and not marker.is_junction():
            with marker.open("rb") as stream:
                if stream.read(len(_RECEIPT_PREFIX)) == _RECEIPT_PREFIX:
                    return candidate
        candidate = candidate.parent
    return None


def completed(destination: Path, identity: str) -> None:
    """Publish a completion marker binding the complete output inventory to its bytes."""
    state = {"schema": 3, "inputs": identity, "outputs": _inventory(destination)}
    (destination / "ready").write_text(json.dumps(state), encoding="utf-8")
