"""One content-keyed product cohort shared by every packaging proof that only reads it.

Several proofs build the same artifacts from the same source: the core-payload
smoke, the split-install sequence and the release-cohort client environment
each built the product wheel and its three data companions, and pytest-xdist
multiplied that by every worker process. A build costs minutes and changes
only when the enumerated source, the selected registry authority, the build
client or the toolchain changes, so the cohort is built once per such content
key and published into the development cache.

Reuse is safe by construction, not by policy. The key names every build input,
the build itself runs from a :func:`~dev.packaging.lane_verification_core.build_root_snapshot`
(never from the live tree), the published key is computed from that snapshot's
own content, so a peer edit landing mid-build cannot file artifacts under a
key they do not represent, and every published artifact is re-hashed against
the recorded digest before it is served. Writers serialise on an OS lock, so
concurrent workers asking for one key build once and the rest wait;
publication itself is an atomic rename, so the lock is never what makes a
served entry correct.
"""

from __future__ import annotations

import contextlib
import functools
import hashlib
import json
import os
import platform
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from cadrumo.core.directory_scan import scan_directory
from dev._paths import REPO_ROOT, UTF_8
from dev.cache_root import dev_cache_dir
from dev.source_tree import content_digest, repository_files

from .authority_staging import selected_published_authority
from .command_execution import run_command
from .google_oauth import build_client_json, client_build_identity
from .hashing import sha256_path
from .lane_verification_core import build_companion_wheels, build_root_snapshot, build_sdist, build_wheel
from .native.action_cache import action_lock

_COHORT_CACHE: Final[str] = "packaging-cohort"
_MANIFEST: Final[str] = "cohort.json"
_SCHEMA: Final[int] = 1
#: Entries kept besides the one in use; older content keys are pruned on publication.
_RETAINED_ENTRIES: Final[int] = 3


@dataclass(frozen=True)
class SharedCohort:
    """Read-only product artifacts built from one fixed source content."""

    key: str
    wheel: Path
    companions: tuple[Path, Path, Path]
    companion_directory: Path
    sdist: Path


def _uv() -> str:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable not found on PATH")
    return uv


def cohort_key(source_root: Path = REPO_ROOT, *, client_root: Path = REPO_ROOT) -> str:
    """Name every input a cohort build consumes, so equal keys mean equal artifacts.

    ``source_root`` is the live tree or a build snapshot of it: a snapshot holds
    the enumerated files with their recorded content plus the staged authority,
    so an unchanged tree and its snapshot share one key. The build client is
    always read from ``client_root``, the checkout a snapshot stages it from.
    """
    source = content_digest(source_root, repository_files(source_root))
    descriptor, database = selected_published_authority(source_root)
    uv_version = run_command([_uv(), "--version"], cwd=client_root)
    if uv_version.returncode != 0:
        raise RuntimeError(f"uv --version failed: {uv_version.stderr}")
    inputs = {
        "schema": _SCHEMA,
        "source": source,
        "authority": [sha256_path(descriptor), sha256_path(database)],
        "build_client": client_build_identity(source, build_client_json(client_root)),
        "python": sys.version,
        "platform": platform.platform(),
        "uv": uv_version.stdout.strip(),
    }
    return hashlib.sha256(json.dumps(inputs, sort_keys=True).encode(UTF_8)).hexdigest()


def _artifact_rows(entry: Path, cohort: SharedCohort) -> dict[str, str]:
    paths = [cohort.wheel, cohort.sdist, *scan_directory(cohort.companion_directory, pattern="*")]
    return {path.relative_to(entry).as_posix(): sha256_path(path) for path in paths}


def _cohort_in(entry: Path, key: str) -> SharedCohort:
    """Locate the artifacts inside one built entry, refusing an incomplete layout."""
    wheels = scan_directory(entry / "wheel", pattern="cadrumo-*.whl")
    sdists = scan_directory(entry / "sdist", pattern="cadrumo-*.tar.gz")
    companion_directory = entry / "companion-wheels"
    companions = tuple(
        scan_directory(companion_directory, pattern=f"cadrumo_data_{label}-*.whl")
        for label in ("manuals", "official", "normatives")
    )
    if len(wheels) != 1 or len(sdists) != 1 or any(len(found) != 1 for found in companions):
        raise RuntimeError(f"cohort entry {entry} does not hold exactly one of each artifact")
    return SharedCohort(
        key=key,
        wheel=wheels[0],
        companions=(companions[0][0], companions[1][0], companions[2][0]),
        companion_directory=companion_directory,
        sdist=sdists[0],
    )


def _verified_entry(entry: Path, key: str) -> SharedCohort | None:
    """Serve a published entry only when every recorded artifact still hashes to its record."""
    try:
        manifest = json.loads((entry / _MANIFEST).read_text(encoding=UTF_8))
        cohort = _cohort_in(entry, key)
    except (OSError, ValueError, RuntimeError):
        return None
    if manifest.get("schema") != _SCHEMA or manifest.get("key") != key:
        return None
    try:
        if _artifact_rows(entry, cohort) != manifest.get("artifacts"):
            return None
    except OSError:
        return None
    return cohort


def _build_from(build_root: Path, work: Path, repo_root: Path, staged: Path, key: str) -> SharedCohort:
    """Build every artifact from ``build_root`` and stage it, with its manifest, in ``staged``."""
    uv = _uv()
    build_wheel(repo_root, work, uv, build_root=build_root)
    build_companion_wheels(work, uv, build_root=build_root)
    build_sdist(work, uv, build_root=build_root)
    staged.mkdir(parents=True)
    for name in ("wheel", "companion-wheels", "sdist"):
        (work / name).replace(staged / name)
    cohort = _cohort_in(staged, key)
    (staged / _MANIFEST).write_text(
        json.dumps({"schema": _SCHEMA, "key": key, "artifacts": _artifact_rows(staged, cohort)}, sort_keys=True),
        encoding=UTF_8,
        newline="\n",
    )
    return cohort


def _publish(cache: Path, staged: Path, key: str) -> SharedCohort:
    """Move ``staged`` into place under ``key``, keeping an equal entry another writer published first."""
    entry = cache / key
    existing = _verified_entry(entry, key)
    if existing is not None:
        shutil.rmtree(staged, ignore_errors=True)
        return existing
    shutil.rmtree(entry, ignore_errors=True)
    staged.replace(entry)
    return _cohort_in(entry, key)


def _prune(cache: Path, keep: str) -> None:
    """Drop older content keys, newest first retained, never the entry in use."""
    entries = [
        path
        for path in cache.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name != keep and (path / _MANIFEST).is_file()
    ]
    entries.sort(key=lambda path: (path / _MANIFEST).stat().st_mtime_ns, reverse=True)
    for stale in entries[_RETAINED_ENTRIES:]:
        shutil.rmtree(stale, ignore_errors=True)
    _prune_locks(cache)


def _prune_locks(cache: Path) -> None:
    # Locks are an optimisation only (publication is an atomic rename of a
    # verified entry), so a lock whose key holds no entry is dropped; a lock
    # still held elsewhere refuses deletion on Windows and is kept.
    live = {path.name for path in cache.iterdir() if path.is_dir()}
    for lock in cache.glob(".*.lock"):
        if lock.name.removeprefix(".").removesuffix(".lock") not in live:
            with contextlib.suppress(OSError):
                lock.unlink()


@functools.lru_cache(maxsize=1)
def shared_cohort(repo_root: Path = REPO_ROOT) -> SharedCohort:
    """Return the product wheel, data companions and sdist for the current source content.

    A miss builds from a fresh snapshot and publishes under the key of the
    content that snapshot actually holds. In a shared worktree the live tree
    moves during a multi-minute build, so keying on the live tree after the
    build would almost never publish; the snapshot's own content is what the
    artifacts represent, and any later reader whose tree holds that content
    finds them.
    """
    cache = dev_cache_dir(_COHORT_CACHE)
    cache.mkdir(parents=True, exist_ok=True)
    requested = cohort_key(repo_root)
    with action_lock(cache, requested):
        cohort = _verified_entry(cache / requested, requested)
        if cohort is not None:
            os.utime(cache / requested / _MANIFEST)
            return cohort
        # Holding this key's lock means no live writer owns its work trees; any
        # left behind belong to an interrupted build.
        for abandoned in cache.glob(f".{requested}.*.work"):
            shutil.rmtree(abandoned, ignore_errors=True)
        work = cache / f".{requested}.{uuid.uuid4().hex}.work"
        try:
            build_root = build_root_snapshot(repo_root, work)
            built = cohort_key(build_root, client_root=repo_root)
            _build_from(build_root, work, repo_root, work / "entry", built)
            cohort = _publish(cache, work / "entry", built)
        finally:
            shutil.rmtree(work, ignore_errors=True)
        _prune(cache, built)
        return cohort


__all__ = ["SharedCohort", "cohort_key", "shared_cohort"]
