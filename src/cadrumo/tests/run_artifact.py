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
import stat
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
    "run_scoped_digest",
]

RUN_ARTIFACT_ROOT_ENV: Final = "CADRUMO_RUN_ARTIFACT_ROOT"
"""Relocates the default cache root for every artifact kind."""
_TEST_RUN_ROOT_ENV: Final = "CADRUMO_TEST_RUN_ROOT"
_DEFAULT_WAIT_SECONDS: Final = 1800.0
_POLL_SECONDS: Final = 0.5
_STAGING_PREFIX: Final = ".staging-"
_DIGESTS_DIRECTORY: Final = ".digests"


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
    return _run_cache_root()


def _run_cache_root() -> Path:
    """Return this pytest run's own cache directory, whatever artifact root override is set."""
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


def run_scoped_digest(
    kind: str,
    compute: Callable[[], str],
    *,
    cache_root: Path | None = None,
    wait_seconds: float = _DEFAULT_WAIT_SECONDS,
) -> str:
    """Return the run's one input digest for ``kind``, computing it only in the first process to ask.

    Taking an artifact's input digest can itself be seconds of hashing, and in a
    shared worktree a peer's edit between two workers' readings would key the
    same artifact twice in one run. The first process therefore computes it under
    the kind's lock and records it beside the run's entries; every other process
    of the run reads the recorded value, so the whole run keys on one snapshot of
    its inputs. The record lives in the run's own cache directory, never the
    artifact root, which persists across runs when overridden, so the next run
    takes a fresh one.
    """
    if not kind or PurePosixPath(kind).name != kind or kind.startswith("."):
        raise ValueError(f"run digest kind must be one plain path segment, got {kind!r}")
    digests = (cache_root or _run_cache_root()) / _DIGESTS_DIRECTORY
    record = digests / f"{kind}.digest"
    if (recorded := _recorded_digest(record)) is not None:
        return recorded
    digests.mkdir(parents=True, exist_ok=True)
    with exclusive_file_lock(digests / kind, timeout=wait_seconds, retry_backoff=_POLL_SECONDS):
        if (recorded := _recorded_digest(record)) is not None:
            return recorded
        digest = compute()
        if not digest.isalnum():
            raise ValueError(f"run digest for {kind} must be alphanumeric, got {digest!r}")
        staging = record.with_name(f"{record.name}{_STAGING_PREFIX}{os.getpid()}")
        staging.write_text(digest, encoding="ascii")
        staging.replace(record)
    return digest


def _recorded_digest(record: Path) -> str | None:
    try:
        recorded = record.read_text(encoding="ascii").strip()
    except (OSError, ValueError):
        return None
    return recorded if recorded.isalnum() else None


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
    """Remove all but the ``retain`` most recent entries; one still open elsewhere is left for later.

    Another worker retiring the same kind can remove an entry between the listing
    and its ``stat``; that entry is already gone, so it is skipped.
    """
    dated: list[tuple[float, Path]] = []
    for path in kind_root.iterdir():
        if path == current or path.name.startswith(_STAGING_PREFIX):
            continue
        try:
            entry_stat = path.stat()
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(entry_stat.st_mode):
            dated.append((entry_stat.st_mtime, path))
    entries = [path for _, path in sorted(dated, key=lambda item: item[0], reverse=True)]
    for stale in entries[max(retain - 1, 0) :]:
        shutil.rmtree(stale, ignore_errors=True)
