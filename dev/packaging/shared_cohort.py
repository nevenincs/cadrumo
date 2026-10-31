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
import re
import shutil
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from cadrumo.core.directory_scan import scan_directory
from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev._paths import REPO_ROOT, UTF_8
from dev.cache_root import dev_cache_dir
from dev.source_tree import normalised_contents, repository_files

from .authority_staging import selected_published_authority
from .build_scratch_reclaim import SHARED_COHORT_WORK_FAMILY, remove_source_snapshot, var_scratch_name
from .command_execution import run_command
from .google_oauth import build_client_json, client_build_identity
from .hashing import sha256_path
from .lane_verification_core import build_companion_wheels, build_root_snapshot, build_sdist, build_wheel
from .native.action_cache import action_lock
from .native.product import distribution_input_digest

_COHORT_CACHE: Final[str] = "packaging-cohort"
_MANIFEST: Final[str] = "cohort.json"
_SCHEMA: Final[int] = 2
#: Entries kept besides the one in use; older content keys are pruned on publication.
_RETAINED_ENTRIES: Final[int] = 3
#: Members a build hook stages from inputs the key names on their own (the published
#: authority and the publisher client), wherever the hook found them.
_SEPARATELY_KEYED_MEMBER: Final = re.compile(
    r"(?:^|/)cadrumo/_data/(?:registry/authority/authority(?:\.current\.json|-[0-9a-f]{64}\.sqlite3)"
    r"|google/oauth_client\.json)$"
)


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


def _companion_projects(source_root: Path) -> tuple[Path, ...]:
    """The data companion projects, read from the declarations the build resolves them by."""
    project = parse_toml((source_root / "pyproject.toml").read_text(encoding=UTF_8))
    sources = project["tool"]["uv"]["sources"]
    return tuple(source_root.joinpath(sources[name]["path"]) for name in PRODUCT_IDENTITY.companion_distributions)


class _BuildVisibleMembers:
    """Select and digest distribution members as a :func:`build_root_snapshot` holds them.

    A cohort is built from a snapshot of the enumerated tree, never from the
    live one, so a member counts only when the snapshot would carry it: a file
    inside the root must be an enumerated repository file, and its bytes are
    the repository-normalised content the snapshot writes. A file a build hook
    stages outside the root (the publisher client) is digested as it is. The
    live tree and a snapshot of it therefore name the same selection.
    """

    def __init__(self, source_root: Path) -> None:
        self.root = source_root.resolve()
        self._enumerated: dict[str, frozenset[str]] = {}

    def _relative(self, path: Path) -> str | None:
        resolved = path.resolve()
        return resolved.relative_to(self.root).as_posix() if resolved.is_relative_to(self.root) else None

    def selected(self, distribution_path: str, path: Path) -> bool:
        if _SEPARATELY_KEYED_MEMBER.search(distribution_path.replace("\\", "/")):
            return False
        relative = self._relative(path)
        if relative is None:
            return True
        top = relative.split("/", 1)[0]
        if top not in self._enumerated:
            self._enumerated[top] = frozenset(repository_files(self.root, under=(top,)))
        return relative in self._enumerated[top]

    def digests(self, paths: Sequence[Path]) -> list[str]:
        relatives = [self._relative(path) for path in paths]
        inside = sorted({relative for relative in relatives if relative is not None})
        normalised = {
            relative: hashlib.sha256(content).hexdigest()
            for relative, content in normalised_contents(self.root, inside)
        }
        return [
            sha256_path(path) if relative is None else normalised[relative]
            for path, relative in zip(paths, relatives, strict=True)
        ]


def cohort_inputs_digest(source_root: Path = REPO_ROOT) -> str:
    """Digest exactly what the cohort's wheel, data companions and sdist are built from.

    Each distribution's members come from its own build backend's selection
    (:func:`~dev.packaging.native.product.distribution_input_digest`): the
    product wheel's packages, the sdist's ``only-include`` set, each companion's
    hook-owned corpus slice, plus metadata and hook implementations. Files no
    distribution selects (the vault, documentation, development tooling, tests)
    are not inputs, so a peer editing them in a shared worktree leaves the key,
    and the published cohort, in place.
    """
    members = _BuildVisibleMembers(source_root)
    projects: list[tuple[Path, Literal["wheel", "sdist"]]] = [(source_root, "wheel"), (source_root, "sdist")]
    projects.extend((project, "wheel") for project in _companion_projects(source_root))
    selected: Callable[[str, Path], bool] = members.selected
    rows = [
        [
            project.resolve().relative_to(members.root).as_posix(),
            target,
            distribution_input_digest(
                project, toolchain=None, target=target, selected=selected, member_digests=members.digests
            ),
        ]
        for project, target in projects
    ]
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode(UTF_8)).hexdigest()


def cohort_key(source_root: Path = REPO_ROOT, *, client_root: Path = REPO_ROOT) -> str:
    """Name every input a cohort build consumes, so equal keys mean equal artifacts.

    ``source_root`` is the live tree or a build snapshot of it: a snapshot holds
    the enumerated files with their recorded content plus the staged authority,
    so an unchanged tree and its snapshot share one key. The build client is
    always read from ``client_root``, the checkout a snapshot stages it from.
    """
    source = cohort_inputs_digest(source_root)
    descriptor, database = selected_published_authority(source_root)
    uv_version = run_command([_uv(), "--version"], cwd=client_root)
    if uv_version.returncode != 0:
        raise RuntimeError(f"uv --version failed: {uv_version.stderr}")
    build_constraint = os.environ.get("UV_BUILD_CONSTRAINT", "")
    inputs = {
        "schema": _SCHEMA,
        "source": source,
        "authority": [sha256_path(descriptor), sha256_path(database)],
        "build_client": client_build_identity(source, build_client_json(client_root)),
        "build_constraint": sha256_path(Path(build_constraint)) if build_constraint != "" else None,
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
        # A dead parent may leave a build subprocess using its work tree. The
        # key lock does not prove that child has stopped, so do not reap peers.
        work = cache / var_scratch_name(SHARED_COHORT_WORK_FAMILY, f"{requested}-{uuid.uuid4().hex}")
        try:
            build_root = build_root_snapshot(repo_root, work)
            built = cohort_key(build_root, client_root=repo_root)
            _build_from(build_root, work, repo_root, work / "entry", built)
            cohort = _publish(cache, work / "entry", built)
        except BaseException as error:
            if work.exists():
                message = f"shared cohort work remains for review: {work}"
                error.add_note(message)
                if isinstance(error, SystemExit):
                    print(message, file=sys.stderr)
            raise
        remove_source_snapshot(work)
        _prune(cache, built)
        return cohort


__all__ = ["SharedCohort", "cohort_inputs_digest", "cohort_key", "shared_cohort"]
