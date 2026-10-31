"""The one run-wide artifact cache: publish once per input digest, verify and reuse everywhere.

An expensive test artifact -- a published authority, a seeded profile, a
documentation build, a whole-tree scan -- is a pure function of its inputs. A
test run therefore produces each distinct one once. The caller names the
artifact's kind and supplies the digest of its real inputs (its own inclusion
policy, never a whole-tree hash the shared worktree churns), a publisher that
writes it into an empty directory, and a cheap verifier. The first process to
ask publishes into a private staging directory under an exclusive lock, the
verified staging directory is renamed into place, and every other process,
xdist worker or later run waits for that lock, verifies the entry and reuses
it. An entry that fails verification is never served: it is removed and
published again.

Entries are read in place. A test that must write takes
:meth:`RunArtifact.writable_copy`, a file copy, never a republication.

The cache root defaults to the run's own cache directory, shared by every
worker of one pytest invocation. A caller whose artifact is worth keeping
across runs passes a persistent root, such as the development cache.

Core-only, so product tests can use it without reaching the development tree.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from cadrumo.core.hashing import content_hash_hex, hash_file
from cadrumo.core.locks import exclusive_file_lock

__all__ = [
    "RUN_ARTIFACT_ROOT_ENV",
    "RunArtifact",
    "file_inputs_digest",
    "run_artifact",
    "run_artifact_root",
]

RUN_ARTIFACT_ROOT_ENV: Final = "CADRUMO_RUN_ARTIFACT_ROOT"
"""Relocates the default cache root for every artifact kind."""
_TEST_RUN_ROOT_ENV: Final = "CADRUMO_TEST_RUN_ROOT"
_DEFAULT_WAIT_SECONDS: Final = 1800.0
_POLL_SECONDS: Final = 0.5
_STAGING_PREFIX: Final = ".staging-"


@dataclass(frozen=True, slots=True)
class RunArtifact:
    """One verified cache entry: the directory holding the artifact and the key it was published under."""

    kind: str
    input_digest: str
    root: Path
    published_by_this_call: bool

    def writable_copy(self, destination: Path) -> Path:
        """Copy the entry's files to ``destination``, which must not exist, and return it."""
        shutil.copytree(self.root, destination, symlinks=False)
        return destination


def run_artifact_root() -> Path:
    """Return the default cache root: the override, else this pytest run's shared cache directory."""
    override = os.environ.get(RUN_ARTIFACT_ROOT_ENV, "").strip()
    if override:
        return Path(override)
    run_root = os.environ.get(_TEST_RUN_ROOT_ENV, "").strip()
    if not run_root:
        raise RuntimeError(
            f"no run artifact root: set {RUN_ARTIFACT_ROOT_ENV} or run under pytest, which sets {_TEST_RUN_ROOT_ENV}"
        )
    return Path(run_root) / "cache" / "run-artifacts"


def file_inputs_digest(kind: str, root: Path, paths: Iterable[Path]) -> str:
    """Digest the root-relative path and content of exactly ``paths``, the artifact's declared inputs."""
    resolved_root = root.resolve()
    entries = sorted(
        [PurePosixPath(*path.resolve().relative_to(resolved_root).parts).as_posix(), hash_file(path)[0]]
        for path in paths
    )
    return content_hash_hex({"schema": "cadrumo-run-artifact-inputs/v1", "kind": kind, "files": entries})


def run_artifact(
    kind: str,
    input_digest: str,
    *,
    publish: Callable[[Path], object],
    verify: Callable[[Path], bool],
    cache_root: Path | None = None,
    retain: int = 3,
    wait_seconds: float = _DEFAULT_WAIT_SECONDS,
) -> RunArtifact:
    """Return the verified entry for ``(kind, input_digest)``, publishing it once if none is current.

    ``publish`` writes the artifact into the empty directory it is given.
    ``verify`` must be cheap -- a digest of the produced bytes, not a rebuild --
    and returns whether a directory holds a correct artifact for this key; it
    gates both reuse and the fresh publication. ``retain`` bounds how many
    entries of this kind survive a new publication, so a concurrent run on
    older inputs keeps its own. A digest is used verbatim as the entry name,
    so callers pass a hex digest, truncated if their paths run long.
    """
    if not kind or PurePosixPath(kind).name != kind or kind.startswith("."):
        raise ValueError(f"run artifact kind must be one plain path segment, got {kind!r}")
    if not input_digest.isalnum():
        raise ValueError(f"run artifact digest must be alphanumeric, got {input_digest!r}")
    kind_root = (cache_root or run_artifact_root()) / kind
    entry = kind_root / input_digest
    if entry.is_dir() and verify(entry):
        return RunArtifact(kind, input_digest, entry, published_by_this_call=False)
    kind_root.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(kind_root / input_digest, timeout=wait_seconds, retry_backoff=_POLL_SECONDS):
        if entry.is_dir():
            if verify(entry):
                return RunArtifact(kind, input_digest, entry, published_by_this_call=False)
            shutil.rmtree(entry)
        staging = kind_root / f"{_STAGING_PREFIX}{input_digest}-{os.getpid()}"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        try:
            publish(staging)
            if not verify(staging):
                raise RuntimeError(f"the {kind} publication for {input_digest} failed its own verification")
            staging.rename(entry)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        _retire(kind_root, current=entry, retain=retain)
    return RunArtifact(kind, input_digest, entry, published_by_this_call=True)


def _retire(kind_root: Path, *, current: Path, retain: int) -> None:
    """Remove all but the ``retain`` most recent entries; one still open elsewhere is left for later."""
    entries = sorted(
        (
            path
            for path in kind_root.iterdir()
            if path.is_dir() and path != current and not path.name.startswith(_STAGING_PREFIX)
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for stale in entries[max(retain - 1, 0) :]:
        shutil.rmtree(stale, ignore_errors=True)
