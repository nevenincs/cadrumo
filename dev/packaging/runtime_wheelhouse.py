"""Build and validate the sealed multi-platform runtime dependency wheelhouse.

The release builder is the sole networked producer. It derives the exact
third-party runtime closure from the tested ``uv.lock``, selects one compatible
wheel for every supported platform, downloads and verifies the lock-recorded
bytes, then writes one deterministic archive. Downstream artifact lanes consume
that archive without resolving dependencies again.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
import urllib.parse
import urllib.request
import uuid
import zipfile
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import Tag
from packaging.utils import canonicalize_name, parse_wheel_filename

from cadrumo.core.directory_scan import scan_directory

from ._hashing import sha256_path
from .uv_constraints import export_runtime_constraints

_UTF_8: Final[str] = "utf-8"
WHEELHOUSE_SCHEMA: Final[str] = "cadrumo.runtime-wheelhouse.v3"
WHEELHOUSE_MANIFEST: Final[str] = "runtime-wheelhouse.json"
WHEELHOUSE_PREFIX: Final[str] = "wheels/"
_ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
_DEFAULT_RUNTIME_ROWS: Final[tuple[tuple[str, bool], ...]] = (
    ("3.13", True),
    ("3.14", True),
    ("3.15", False),
)
_PYTHON_MINOR_RE: Final[re.Pattern[str]] = re.compile(r"^3\.(?P<minor>[0-9]+)$")
_DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 180.0
_DOWNLOAD_WORKERS: Final[int] = 8
_CACHE_DIR_ENV: Final[str] = "CADRUMO_RUNTIME_WHEEL_CACHE_DIR"
_CACHE_BYTES_ENV: Final[str] = "CADRUMO_RUNTIME_WHEEL_CACHE_BYTES"
_DEFAULT_CACHE_BYTES: Final[int] = 8 * 1024**3
"""Byte ceiling on the runner-local wheel cache.

Sized against what it holds rather than against a round number: one build's
closure spans four platforms and three runtimes and lands near two gigabytes,
so eight leaves a few consecutive locks resident and still bounds the store at
a fraction of a development volume.
"""


@dataclass(frozen=True)
class TargetPlatform:
    """One supported installation target and its marker environment."""

    name: str
    sys_platform: str
    platform_system: str
    platform_machine: str
    os_name: str
    floor: str


#: The Linux floors are 2.28, NOT the manylinux2014 baseline of 2.17.
#
# 2.17 was unsatisfiable, and had been since the ecosystem moved off it. The
# cohort build failed with
#
#     runtime lock has no linux-aarch64 wheel for argon2-cffi-bindings==26.1.0
#
# which reads as a missing wheel and is not one: the lock carries
# `argon2_cffi_bindings-26.1.0-cp310-abi3-manylinux_2_26_aarch64`, and 2.26 is
# above a 2.17 floor, so nothing selectable existed. There is no 2.17 Linux
# wheel for this package at any version in the lock, so the floor could not be
# met by choosing differently - only by moving it. x86-64 sits behind the same
# wall and merely failed second, aarch64 being first in this tuple.
#
# 2.28 is chosen rather than 2.26 because it is what the rest of this fleet
# already promises: vaultspec-core, vaultspec-rag and vaultspec-dashboard all
# pin their Linux builds to a digest-pinned manylinux_2_28 image and measure
# 2.28 out of the published artifact. It covers RHEL 8, Rocky 8, Alma 8,
# Debian 10+, Ubuntu 20.04+ and Amazon Linux 2023, and it satisfies the 2.26
# wheels above with headroom.
#
# What this drops is glibc 2.17-era platforms - RHEL 7 and CentOS 7, both long
# past end of life. That is a real narrowing and is stated here rather than
# left implicit.
SUPPORTED_TARGETS: Final[tuple[TargetPlatform, ...]] = (
    TargetPlatform("linux-aarch64", "linux", "Linux", "aarch64", "posix", "glibc-2.28"),
    TargetPlatform("linux-x86-64", "linux", "Linux", "x86_64", "posix", "glibc-2.28"),
    # The macOS floor is 14.0, NOT 11.0, and this is the same class of defect the
    # Linux floors carried: a declared floor no wheel could satisfy.
    #
    # `python_cohort build` failed with
    #
    #     runtime lock has no macos-arm64 wheel for pikepdf==10.12.0
    #
    # which reads as a missing wheel and is not one. pikepdf 10.12.0 publishes
    # six macOS arm64 wheels and every one of them is `macosx_14_0_arm64`;
    # `_platform_rank` rejects any wheel whose minimum exceeds the declared
    # floor, so at 11.0 the entire set was unselectable and the lock looked
    # empty. numpy and scipy are in exactly the same position - all three now
    # ship arm64 wheels that require macOS 14.
    #
    # What this drops is macOS 11 (Big Sur), 12 (Monterey) and 13 (Ventura).
    # That is a real narrowing and is stated here rather than left implicit. It
    # follows upstream rather than leading it: the alternative is pinning numpy,
    # scipy and pikepdf backwards to reach older wheels, which is a dependency
    # decision with a much wider blast radius than a floor change.
    TargetPlatform("macos-arm64", "darwin", "Darwin", "arm64", "posix", "macos-14.0"),
    TargetPlatform("windows-x86-64", "win32", "Windows", "AMD64", "nt", "windows-10"),
)
PLATFORM_FLOORS: Final[dict[str, str]] = {target.name: target.floor for target in SUPPORTED_TARGETS}


@dataclass(frozen=True)
class LockedWheel:
    """One exact lock-recorded wheel selected for at least one target."""

    distribution: str
    version: str
    filename: str
    url: str
    sha256: str
    size: int


@dataclass(frozen=True)
class RuntimeWheelhousePlan:
    """The selected wheels and target rows for one Python minor."""

    python_version: str
    platforms: dict[str, dict[str, str]]
    wheels: tuple[LockedWheel, ...]
    missing: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class RuntimeWheelhouse:
    """Validated wheelhouse archive paired with its strict manifest."""

    archive: Path
    manifest: dict[str, Any]


def _canonical_python_minor(value: str) -> str:
    """Return one canonical ``3.N`` runtime key from a selector or minor."""
    match = _PYTHON_MINOR_RE.fullmatch(value) or re.fullmatch(r"3\.(?P<minor>[0-9]+)\.[0-9]+", value)
    if match is None:
        raise SystemExit(f"runtime wheelhouse Python selector is not a CPython 3.x minor: {value!r}")
    return f"3.{int(match.group('minor'))}"


def _runtime_rows(repo_root: Path, python_versions: Sequence[str] | None) -> tuple[tuple[str, bool], ...]:
    """Return stable and advisory runtime rows from the canonical inventory."""
    if python_versions is not None:
        rows = tuple((_canonical_python_minor(value), True) for value in python_versions)
    else:
        inventory_path = repo_root / "dev" / "ci" / "python-runtime-matrix.json"
        if not inventory_path.is_file():
            rows = _DEFAULT_RUNTIME_ROWS
        else:
            try:
                from ..ci.python_runtime_matrix import RuntimeMatrixError, load_runtime_inventory

                inventory = load_runtime_inventory(inventory_path)
            except RuntimeMatrixError as exc:
                raise SystemExit(f"runtime inventory cannot drive wheelhouse construction: {exc}") from exc
            rows = (*((row.minor, True) for row in inventory.stable), (inventory.next.minor, False))
    if not rows:
        raise SystemExit("runtime wheelhouse runtime set is empty")
    if len({minor for minor, _blocking in rows}) != len(rows):
        raise SystemExit(f"runtime wheelhouse runtime set contains duplicates: {rows!r}")
    return rows


def _marker_environment(target: TargetPlatform, python_version: str) -> dict[str, str]:
    python_minor = _canonical_python_minor(python_version)
    python_full_version = f"{python_minor}.0"
    environment = dict(default_environment())
    environment.update(
        {
            "implementation_name": "cpython",
            "implementation_version": python_full_version,
            "os_name": target.os_name,
            "platform_machine": target.platform_machine,
            "platform_python_implementation": "CPython",
            "platform_system": target.platform_system,
            "python_full_version": python_full_version,
            "python_version": python_minor,
            "sys_platform": target.sys_platform,
        }
    )
    return environment


def _interpreter_rank(tag: Tag, python_version: str) -> int | None:
    target_minor = int(_canonical_python_minor(python_version).split(".", maxsplit=1)[1])
    target_interpreter = f"cp3{target_minor}"
    interpreter = tag.interpreter
    abi = tag.abi
    if interpreter in {"py3", f"py3{target_minor}"} and abi == "none":
        return 0
    if interpreter == target_interpreter and abi == target_interpreter:
        return 1
    if interpreter == target_interpreter and abi == "abi3":
        return 2
    if interpreter.startswith("cp3") and interpreter[3:].isdigit() and abi == "abi3":
        minor = int(interpreter[3:])
        if minor <= target_minor:
            return 3 + (target_minor - minor)
    return None


def _manylinux_floor(platform: str, architecture: str) -> tuple[int, int] | None:
    aliases = {
        f"manylinux1_{architecture}": (2, 5),
        f"manylinux2010_{architecture}": (2, 12),
        f"manylinux2014_{architecture}": (2, 17),
    }
    if platform in aliases:
        return aliases[platform]
    match = re.fullmatch(rf"manylinux_(\d+)_(\d+)_{re.escape(architecture)}", platform)
    return (int(match.group(1)), int(match.group(2))) if match else None


#: `glibc-2.28` -> (2, 28); `macos-11.0` -> (11, 0); `windows-10` -> (10, 0).
_DECLARED_FLOOR = re.compile(r"^[a-z]+-(\d+)(?:\.(\d+))?$")


def _declared_floor(target: TargetPlatform) -> tuple[int, int]:
    """Return the floor this target DECLARES, as the version that gates wheels.

    The declared floor used to be documentation only: `SUPPORTED_TARGETS` fed
    `PLATFORM_FLOORS` into the cohort manifest, while :func:`_platform_rank`
    enforced hard-coded literals of its own - `(2, 17)` for Linux and `(11, 0)`
    for macOS. Two independent numbers describing one policy, free to disagree,
    and they did: raising the declared Linux floor to 2.28 changed the published
    manifest and not one wheel decision.

    Reading it here collapses them. What the manifest promises is now what the
    selector applies, and a floor change is a real change rather than a caption.
    """
    match = _DECLARED_FLOOR.fullmatch(target.floor)
    if match is None:
        raise SystemExit(f"target {target.name} declares an unparsable floor: {target.floor!r}")
    return (int(match.group(1)), int(match.group(2) or 0))


def _platform_rank(platform: str, target: TargetPlatform) -> int | None:
    if platform == "any":
        return 0
    if target.name == "windows-x86-64":
        return 10_000 if platform == "win_amd64" else None
    if target.name == "macos-arm64":
        match = re.fullmatch(r"macosx_(\d+)_(\d+)_(arm64|universal2)", platform)
        if match is None:
            return None
        minimum = (int(match.group(1)), int(match.group(2)))
        if minimum > _declared_floor(target):
            return None
        return 10_000 + minimum[0] * 100 + minimum[1]
    architecture = "x86_64" if target.name == "linux-x86-64" else "aarch64"
    minimum_glibc = _manylinux_floor(platform, architecture)
    if minimum_glibc is None or minimum_glibc > _declared_floor(target):
        return None
    return 10_000 + minimum_glibc[0] * 100 + minimum_glibc[1]


def _wheel_rank(filename: str, target: TargetPlatform, python_version: str) -> tuple[int, int, int] | None:
    try:
        _name, _version, _build, tags = parse_wheel_filename(filename)
    except ValueError:
        return None
    ranks = []
    for tag in tags:
        interpreter_rank = _interpreter_rank(tag, python_version)
        platform_rank = _platform_rank(tag.platform, target)
        if interpreter_rank is not None and platform_rank is not None:
            ranks.append((0 if platform_rank == 0 else 1, interpreter_rank, -platform_rank))
    return min(ranks) if ranks else None


def _wheel_filename(url: str) -> str:
    filename = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).name
    if not filename.endswith(".whl") or Path(filename).name != filename:
        raise SystemExit(f"lock wheel URL has an invalid filename: {url!r}")
    return filename


def _active_requirements(repo_root: Path, target: TargetPlatform, python_version: str) -> dict[str, Requirement]:
    environment = _marker_environment(target, python_version)
    active: dict[str, Requirement] = {}
    for line in export_runtime_constraints(repo_root=repo_root):
        requirement = Requirement(line)
        if requirement.marker is not None and not requirement.marker.evaluate(environment=environment):
            continue
        name = canonicalize_name(requirement.name)
        previous = active.get(name)
        if previous is not None and str(previous) != str(requirement):
            raise SystemExit(
                f"runtime lock exports multiple active requirements for {name!r} on {target.name}: "
                f"{previous!s}, {requirement!s}"
            )
        active[name] = requirement
    if not active:
        raise SystemExit(f"runtime lock exported no active requirements for {target.name}")
    return active


def _plan_runtime_wheelhouse(repo_root: Path, python_version: str) -> RuntimeWheelhousePlan:
    """Resolve one runtime's exact lock wheels across every supported platform."""
    root = repo_root.resolve(strict=True)
    python_minor = _canonical_python_minor(python_version)
    lock = tomllib.loads((root / "uv.lock").read_text(encoding=_UTF_8))
    by_name: dict[str, list[dict[str, Any]]] = {}
    for package in lock.get("package", []):
        if isinstance(package, dict) and isinstance(package.get("name"), str):
            by_name.setdefault(canonicalize_name(package["name"]), []).append(package)
    selected: dict[str, LockedWheel] = {}
    platforms: dict[str, dict[str, str]] = {}
    missing: list[dict[str, str]] = []
    for target in SUPPORTED_TARGETS:
        target_rows: dict[str, str] = {}
        for name, requirement in sorted(_active_requirements(root, target, python_minor).items()):
            candidates = [
                package
                for package in by_name.get(name, [])
                if isinstance(package.get("version"), str)
                and requirement.specifier.contains(str(package["version"]), prereleases=True)
                and package.get("source", {}).get("registry") == "https://pypi.org/simple"
            ]
            if len(candidates) != 1:
                raise SystemExit(
                    f"runtime lock must contain one registry package for {requirement!s}: "
                    f"{[(item.get('version'), item.get('source')) for item in candidates]!r}"
                )
            package = candidates[0]
            wheels: list[tuple[tuple[int, int, int], str, str, str, int]] = []
            for raw in package.get("wheels", []):
                if not isinstance(raw, dict):
                    continue
                url = raw.get("url")
                digest = raw.get("hash")
                size = raw.get("size")
                if not isinstance(url, str) or not isinstance(digest, str) or not isinstance(size, int):
                    continue
                filename = _wheel_filename(url)
                rank = _wheel_rank(filename, target, python_minor)
                if rank is not None:
                    wheels.append((rank, filename, url, digest.removeprefix("sha256:"), size))
            if not wheels:
                missing.append(
                    {
                        "distribution": name,
                        "platform": target.name,
                        "reason": "no-compatible-wheel",
                        "requirement": str(requirement),
                    }
                )
                continue
            # Compatibility rank is authoritative: universal first, then the
            # exact CPython/ABI order and closest platform tag at or below the
            # declared OS floor. Filename only breaks an equivalent-tag tie.
            wheels.sort(key=lambda item: (item[0], item[1]))
            _rank, filename, url, digest, size = wheels[0]
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise SystemExit(f"runtime lock wheel digest is invalid for {filename!r}")
            wheel = LockedWheel(
                distribution=name,
                version=str(package["version"]),
                filename=filename,
                url=url,
                sha256=digest,
                size=size,
            )
            previous = selected.get(filename)
            if previous is not None and previous != wheel:
                raise SystemExit(f"runtime lock assigns conflicting bytes to {filename!r}")
            selected[filename] = wheel
            target_rows[name] = filename
        platforms[target.name] = target_rows
    return RuntimeWheelhousePlan(
        python_version=python_minor,
        platforms=platforms,
        wheels=tuple(selected[name] for name in sorted(selected)),
        missing=tuple(missing),
    )


def _missing_wheel_message(plan: RuntimeWheelhousePlan) -> str:
    missing = "; ".join(f"{item['distribution']} ({item['platform']}, {item['requirement']})" for item in plan.missing)
    return f"runtime lock has no complete {plan.python_version} wheelhouse: {missing}"


def plan_runtime_wheelhouse(
    repo_root: Path,
    *,
    python_version: str = "3.13",
) -> tuple[dict[str, dict[str, str]], tuple[LockedWheel, ...]]:
    """Resolve the exact lock wheels for one Python minor and all platforms."""
    plan = _plan_runtime_wheelhouse(repo_root, python_version)
    if plan.missing:
        raise SystemExit(_missing_wheel_message(plan))
    return plan.platforms, plan.wheels


def plan_runtime_wheelhouses(
    repo_root: Path,
    *,
    python_versions: Sequence[str] | None = None,
) -> dict[str, RuntimeWheelhousePlan]:
    """Resolve every requested runtime, retaining advisory missing-wheel rows."""
    root = repo_root.resolve(strict=True)
    plans: dict[str, RuntimeWheelhousePlan] = {}
    for python_version, blocking in _runtime_rows(root, python_versions):
        plan = _plan_runtime_wheelhouse(root, python_version)
        if plan.missing and blocking:
            raise SystemExit(_missing_wheel_message(plan))
        plans[plan.python_version] = plan
    return plans


def _manifest_document(
    repo_root: Path,
    *,
    python_versions: Sequence[str] | None = None,
) -> tuple[dict[str, Any], tuple[RuntimeWheelhousePlan, ...]]:
    plans_by_runtime = plan_runtime_wheelhouses(repo_root, python_versions=python_versions)
    entries: dict[str, dict[str, Any]] = {}
    ready_plans: list[RuntimeWheelhousePlan] = []
    for python_version, plan in sorted(plans_by_runtime.items()):
        if plan.missing:
            entries[python_version] = {
                "missing": list(plan.missing),
                "python": python_version,
                "status": "missing-wheel",
            }
            continue
        ready_plans.append(plan)
        entries[python_version] = {
            "platforms": plan.platforms,
            "python": python_version,
            "status": "ready",
            "wheels": {
                wheel.filename: {
                    "distribution": wheel.distribution,
                    "sha256": wheel.sha256,
                    "size": wheel.size,
                    "version": wheel.version,
                }
                for wheel in plan.wheels
            },
        }
    return (
        {
            "lock_sha256": sha256_path(repo_root / "uv.lock"),
            "platform_floors": PLATFORM_FLOORS,
            "runtimes": entries,
            "schema": WHEELHOUSE_SCHEMA,
        },
        tuple(ready_plans),
    )


def _download(wheel: LockedWheel, destination: Path) -> None:
    digest = hashlib.sha256()
    size = 0
    with (
        urllib.request.urlopen(wheel.url, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response,  # noqa: S310
        destination.open("xb") as handle,
    ):
        while chunk := response.read(1024 * 1024):
            handle.write(chunk)
            digest.update(chunk)
            size += len(chunk)
    if size != wheel.size or digest.hexdigest() != wheel.sha256:
        destination.unlink(missing_ok=True)
        raise SystemExit(
            f"downloaded runtime wheel drifted for {wheel.filename!r}: "
            f"expected size/digest {wheel.size}/{wheel.sha256}, got {size}/{digest.hexdigest()}"
        )


def wheel_cache_dir() -> Path | None:
    """Return the runner-local wheel cache directory, or ``None`` when disabled.

    Follows the proof cache's convention: an explicit
    ``CADRUMO_RUNTIME_WHEEL_CACHE_DIR`` wins, otherwise ``~/.cadrumo`` holds it.
    Setting the variable to an empty value disables caching outright, which is
    what a run that must prove it fetched from the index sets.

    The cache is safe by construction rather than by policy: every entry is
    named for the SHA-256 the lock records, and is re-hashed against that name
    before it is served. There is no invalidation question to get wrong -- a
    lock change asks for a different digest, so it addresses a different entry.
    """
    override = os.environ.get(_CACHE_DIR_ENV)
    if override is not None:
        return Path(override) if override.strip() else None
    return Path.home() / ".cadrumo" / "runtime-wheel-cache"


def _cache_entry(cache: Path, wheel: LockedWheel) -> Path:
    return cache / wheel.sha256


def _serve_from_cache(cache: Path | None, wheel: LockedWheel, destination: Path) -> bool:
    """Copy ``wheel`` out of ``cache`` when the cached bytes still prove out."""
    if cache is None:
        return False
    entry = _cache_entry(cache, wheel)
    try:
        if entry.stat().st_size != wheel.size or sha256_path(entry) != wheel.sha256:
            return False
        shutil.copyfile(entry, destination)
    except OSError:
        return False
    return True


def _store_in_cache(cache: Path | None, wheel: LockedWheel, source: Path) -> None:
    """Publish verified bytes into the cache, tolerating any storage refusal.

    Written to a neighbour unique to this WRITE and moved into place, so a
    reader never observes a partially written entry, and a loser of a race
    between two writers overwrites an identical file rather than corrupting
    one. Unique per write rather than per process, because the writers that
    meet here most often are threads of one process: the runtimes select the
    same universal wheels, so a process identifier alone gave several workers
    one staging path, and on Windows the ensuing replace fails with a sharing
    violation that this function then swallows.
    """
    if cache is None:
        return
    entry = _cache_entry(cache, wheel)
    staging = entry.with_name(f".{entry.name}.{os.getpid()}.{uuid.uuid4().hex}.partial")
    try:
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, staging)
        staging.replace(entry)
    except OSError:
        with contextlib.suppress(OSError):
            staging.unlink(missing_ok=True)


def _acquire(wheel: LockedWheel, destination: Path, cache: Path | None) -> bool:
    """Place ``wheel``'s exact lock-recorded bytes at ``destination``.

    Returns:
        Whether the bytes came from the cache rather than the index.
    """
    if _serve_from_cache(cache, wheel, destination):
        return True
    _download(wheel, destination)
    _store_in_cache(cache, wheel, destination)
    return False


def grouped_wheel_requests(
    plans: Sequence[RuntimeWheelhousePlan],
) -> tuple[tuple[LockedWheel, tuple[Path, ...]], ...]:
    """Collapse every runtime's selection into one request per distinct wheel.

    Keyed on the lock-recorded SHA-256, which is what makes two runtimes'
    selections the same bytes rather than merely the same filename. The
    destinations are kept in encounter order so the runtime that first asked
    for a wheel is the one it is fetched into.

    Returns:
        One ``(wheel, destinations)`` pair per distinct digest, each carrying
        every runtime directory that wheel belongs in.
    """
    grouped: dict[str, tuple[LockedWheel, list[Path]]] = {}
    for plan in plans:
        for wheel in plan.wheels:
            _selected, destinations = grouped.setdefault(wheel.sha256, (wheel, []))
            destinations.append(Path(plan.python_version) / wheel.filename)
    return tuple((wheel, tuple(destinations)) for wheel, destinations in grouped.values())


def _acquire_group(wheel: LockedWheel, destinations: Sequence[Path], cache: Path | None) -> None:
    """Obtain one wheel's bytes once and place them in every runtime that selected it."""
    primary, *copies = destinations
    _acquire(wheel, primary, cache)
    for copy in copies:
        shutil.copyfile(primary, copy)


def _acquire_all(
    plans: Sequence[RuntimeWheelhousePlan],
    wheel_dir: Path,
    cache: Path | None,
) -> None:
    """Fetch every selected wheel for every runtime, in parallel and once each.

    Two distinct repetitions are removed here. Within one build the runtimes
    overwhelmingly select the SAME universal wheels, so a serial pass over
    ``plans`` fetched identical bytes up to three times; :func:`
    grouped_wheel_requests` collapses that to one fetch plus local copies
    BEFORE anything is submitted. Deduplicating at submission rather than
    leaving it to the cache is what makes the collapse real: three workers
    holding one digest all miss the empty cache together, so each of them
    downloads, and their stores then race for one entry.

    Across builds an unchanged lock asks for exactly the digests the previous
    build already stored, which is the repetition the cache removes.

    Concurrency is deliberately modest. The index is a shared service and the
    work is entirely network-bound, so a small pool removes the round-trip
    stalls without turning a release build into a load generator.
    """
    failures: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=_DOWNLOAD_WORKERS) as pool:
        futures = [
            pool.submit(_acquire_group, wheel, tuple(wheel_dir / relative for relative in destinations), cache)
            for wheel, destinations in grouped_wheel_requests(plans)
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except BaseException as exc:
                # Collected rather than raised here so every worker settles
                # first: a raise inside the pool's context leaves the remaining
                # futures to be cancelled mid-write. The first failure is
                # re-raised below with its own traceback intact.
                failures.append(exc)
    if failures:
        raise failures[0]


def prune_wheel_cache(cache: Path | None, *, limit_bytes: int | None = None) -> int:
    """Evict oldest-first until the cache fits its byte ceiling; return bytes removed.

    Every persistent cache in this repository is bounded. Bounded by BYTES
    rather than by entry count because the entries are wheels spanning four
    orders of magnitude in size, so a count cap says nothing about the disk a
    cache occupies. Eviction is by modification time, which a cache hit does not
    refresh -- an entry's age is therefore its age since it was fetched, and the
    ceiling bounds the store rather than modelling reuse.
    """
    if cache is None:
        return 0
    ceiling = _cache_limit_bytes() if limit_bytes is None else limit_bytes
    try:
        entries = [(path, path.stat()) for path in scan_directory(cache) if path.is_file()]
    except OSError:
        return 0
    total = sum(stat.st_size for _path, stat in entries)
    if total <= ceiling:
        return 0
    removed = 0
    for path, stat in sorted(entries, key=lambda item: item[1].st_mtime):
        if total - removed <= ceiling:
            break
        with contextlib.suppress(OSError):
            path.unlink()
            removed += stat.st_size
    return removed


def _cache_limit_bytes() -> int:
    raw = os.environ.get(_CACHE_BYTES_ENV, "").strip()
    if not raw:
        return _DEFAULT_CACHE_BYTES
    try:
        value = int(raw)
    except ValueError as exc:
        raise SystemExit(f"{_CACHE_BYTES_ENV} must be an integer byte count: {raw!r}") from exc
    if value < 0:
        raise SystemExit(f"{_CACHE_BYTES_ENV} must not be negative: {value}")
    return value


def build_runtime_wheelhouse(
    repo_root: Path,
    destination: Path,
    *,
    python_versions: Sequence[str] | None = None,
) -> RuntimeWheelhouse:
    """Download lock-selected wheels and write one deterministic multi-runtime archive."""
    root = repo_root.resolve(strict=True)
    output = destination.resolve()
    if output.exists():
        raise FileExistsError(output)
    manifest, plans = _manifest_document(root, python_versions=python_versions)
    output.parent.mkdir(parents=True, exist_ok=True)
    cache = wheel_cache_dir()
    with tempfile.TemporaryDirectory(prefix="cadrumo-runtime-wheelhouse-") as temporary:
        wheel_dir = Path(temporary)
        for plan in plans:
            (wheel_dir / plan.python_version).mkdir()
        _acquire_all(plans, wheel_dir, cache)
        prune_wheel_cache(cache)
        with zipfile.ZipFile(output, mode="x", compression=zipfile.ZIP_STORED) as archive:
            manifest_info = zipfile.ZipInfo(WHEELHOUSE_MANIFEST, date_time=_ZIP_TIMESTAMP)
            manifest_info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                manifest_info,
                json.dumps(manifest, indent=2, sort_keys=True).encode(_UTF_8) + b"\n",
            )
            for plan in plans:
                for wheel in plan.wheels:
                    info = zipfile.ZipInfo(
                        f"{WHEELHOUSE_PREFIX}{plan.python_version}/{wheel.filename}",
                        date_time=_ZIP_TIMESTAMP,
                    )
                    info.external_attr = (0o100644 & 0xFFFF) << 16
                    archive.writestr(info, (wheel_dir / plan.python_version / wheel.filename).read_bytes())
    return load_runtime_wheelhouse(output, expected_lock_sha256=manifest["lock_sha256"])


def load_runtime_wheelhouse(
    archive_path: Path,
    *,
    expected_lock_sha256: str | None = None,
    expected_python: str | None = None,
) -> RuntimeWheelhouse:
    """Validate a closed multi-runtime wheelhouse archive and every wheel byte."""
    archive = archive_path.resolve(strict=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if names.count(WHEELHOUSE_MANIFEST) != 1 or len(names) != len(set(names)):
            raise SystemExit("runtime wheelhouse has a missing or duplicate manifest/member")
        manifest = json.loads(bundle.read(WHEELHOUSE_MANIFEST))
        if not isinstance(manifest, dict) or set(manifest) != {
            "lock_sha256",
            "platform_floors",
            "runtimes",
            "schema",
        }:
            raise SystemExit("runtime wheelhouse manifest schema drifted")
        if manifest.get("schema") != WHEELHOUSE_SCHEMA:
            raise SystemExit("runtime wheelhouse identity drifted")
        if manifest.get("platform_floors") != PLATFORM_FLOORS:
            raise SystemExit("runtime wheelhouse platform support floor drifted")
        lock_sha256 = manifest.get("lock_sha256")
        if not isinstance(lock_sha256, str) or len(lock_sha256) != 64:
            raise SystemExit("runtime wheelhouse lock digest is invalid")
        if expected_lock_sha256 is not None and lock_sha256 != expected_lock_sha256:
            raise SystemExit("runtime wheelhouse does not bind the tested uv.lock")
        runtimes = manifest.get("runtimes")
        if not isinstance(runtimes, dict) or not runtimes:
            raise SystemExit("runtime wheelhouse declares no runtimes")
        if expected_python is not None:
            expected_runtime = _canonical_python_minor(expected_python)
            if expected_runtime not in runtimes:
                raise SystemExit(f"runtime wheelhouse has no entry for Python {expected_runtime}")
            selected = runtimes[expected_runtime]
            if not isinstance(selected, dict) or selected.get("status") != "ready":
                raise SystemExit(f"runtime wheelhouse has no ready entry for Python {expected_runtime}")

        declared = {WHEELHOUSE_MANIFEST}
        for python_version, runtime in runtimes.items():
            canonical_runtime = _canonical_python_minor(python_version) if isinstance(python_version, str) else ""
            if canonical_runtime != python_version or not isinstance(runtime, dict):
                raise SystemExit(f"runtime wheelhouse runtime declaration is invalid: {python_version!r}")
            status = runtime.get("status")
            if runtime.get("python") != python_version:
                raise SystemExit(f"runtime wheelhouse runtime identity drifted: {python_version!r}")
            if status == "missing-wheel":
                if set(runtime) != {"missing", "python", "status"}:
                    raise SystemExit(f"runtime wheelhouse missing-wheel record drifted: {python_version!r}")
                missing = runtime.get("missing")
                if not isinstance(missing, list) or not missing:
                    raise SystemExit(f"runtime wheelhouse missing-wheel record is empty: {python_version!r}")
                for item in missing:
                    if (
                        not isinstance(item, dict)
                        or set(item)
                        != {
                            "distribution",
                            "platform",
                            "reason",
                            "requirement",
                        }
                        or any(not isinstance(item[key], str) or not item[key] for key in item)
                    ):
                        raise SystemExit(f"runtime wheelhouse missing-wheel attribution is invalid: {python_version!r}")
                continue
            if status != "ready" or set(runtime) != {"platforms", "python", "status", "wheels"}:
                raise SystemExit(f"runtime wheelhouse runtime status is invalid: {python_version!r}")
            platforms = runtime.get("platforms")
            wheels = runtime.get("wheels")
            if not isinstance(platforms, dict) or set(platforms) != {target.name for target in SUPPORTED_TARGETS}:
                raise SystemExit(f"runtime wheelhouse platform closure is incomplete: {python_version!r}")
            if not isinstance(wheels, dict) or not wheels:
                raise SystemExit(f"runtime wheelhouse declares no wheels: {python_version!r}")
            for filename, raw in wheels.items():
                if not isinstance(filename, str) or Path(filename).name != filename or not filename.endswith(".whl"):
                    raise SystemExit(f"runtime wheelhouse wheel declaration is invalid: {filename!r}")
                if not isinstance(raw, dict) or set(raw) != {"distribution", "sha256", "size", "version"}:
                    raise SystemExit(f"runtime wheelhouse wheel record drifted: {filename!r}")
                digest = raw.get("sha256")
                if (
                    not isinstance(digest, str)
                    or len(digest) != 64
                    or any(character not in "0123456789abcdef" for character in digest)
                    or not isinstance(raw.get("size"), int)
                    or raw["size"] < 0
                    or not isinstance(raw.get("distribution"), str)
                    or not raw["distribution"]
                    or not isinstance(raw.get("version"), str)
                    or not raw["version"]
                ):
                    raise SystemExit(f"runtime wheelhouse wheel record is invalid: {filename!r}")
                member = f"{WHEELHOUSE_PREFIX}{python_version}/{filename}"
                declared.add(member)
                payload = bundle.read(member)
                if len(payload) != raw["size"] or hashlib.sha256(payload).hexdigest() != digest:
                    raise SystemExit(f"runtime wheelhouse wheel bytes drifted: {python_version}/{filename!r}")
            for target, rows in platforms.items():
                if not isinstance(rows, dict) or not rows:
                    raise SystemExit(f"runtime wheelhouse target closure is empty: {python_version}/{target!r}")
                for distribution, filename in rows.items():
                    record = wheels.get(filename) if isinstance(filename, str) else None
                    if (
                        not isinstance(distribution, str)
                        or not distribution
                        or not isinstance(filename, str)
                        or not isinstance(record, dict)
                        or record.get("distribution") != distribution
                    ):
                        raise SystemExit(
                            f"runtime wheelhouse target references an unknown wheel: {python_version}/{target!r}"
                        )
        if set(names) != declared:
            raise SystemExit("runtime wheelhouse member inventory drifted")
    return RuntimeWheelhouse(archive=archive, manifest=manifest)


def extract_runtime_wheelhouse(
    archive_path: Path,
    destination: Path,
    *,
    python_version: str | None = None,
) -> RuntimeWheelhouse:
    """Validate then extract one ready runtime's wheel bytes into a directory."""
    wheelhouse = load_runtime_wheelhouse(archive_path, expected_python=python_version)
    runtimes = wheelhouse.manifest["runtimes"]
    ready = [name for name, value in runtimes.items() if isinstance(value, dict) and value.get("status") == "ready"]
    if python_version is None:
        if len(ready) != 1:
            raise SystemExit("runtime-specific wheelhouse extraction requires --python-version")
        selected_runtime = ready[0]
    else:
        selected_runtime = _canonical_python_minor(python_version)
    runtime = runtimes.get(selected_runtime)
    if not isinstance(runtime, dict) or runtime.get("status") != "ready":
        raise SystemExit(f"runtime wheelhouse has no ready entry for Python {selected_runtime}")
    target = destination.resolve()
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    wheels = runtime["wheels"]
    with zipfile.ZipFile(wheelhouse.archive) as bundle:
        for filename in sorted(wheels):
            (target / filename).write_bytes(bundle.read(f"{WHEELHOUSE_PREFIX}{selected_runtime}/{filename}"))
        (target / WHEELHOUSE_MANIFEST).write_text(
            json.dumps(wheelhouse.manifest, indent=2, sort_keys=True) + "\n",
            encoding=_UTF_8,
            newline="\n",
        )
    return wheelhouse


__all__ = [
    "PLATFORM_FLOORS",
    "SUPPORTED_TARGETS",
    "WHEELHOUSE_MANIFEST",
    "WHEELHOUSE_PREFIX",
    "WHEELHOUSE_SCHEMA",
    "RuntimeWheelhouse",
    "RuntimeWheelhousePlan",
    "build_runtime_wheelhouse",
    "extract_runtime_wheelhouse",
    "load_runtime_wheelhouse",
    "plan_runtime_wheelhouse",
    "plan_runtime_wheelhouses",
]
