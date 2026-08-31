"""Build and validate the sealed multi-platform runtime dependency wheelhouse.

The release builder is the sole networked producer. It derives the exact
third-party runtime closure from the tested ``uv.lock``, selects one compatible
wheel for every supported platform, downloads and verifies the lock-recorded
bytes, then writes one deterministic archive. Downstream artifact lanes consume
that archive without resolving dependencies again.
"""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import tomllib
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import Tag
from packaging.utils import canonicalize_name, parse_wheel_filename

from ._hashing import sha256_path
from .uv_constraints import export_runtime_constraints

_UTF_8: Final[str] = "utf-8"
WHEELHOUSE_SCHEMA: Final[str] = "cadrumo.runtime-wheelhouse.v2"
WHEELHOUSE_MANIFEST: Final[str] = "runtime-wheelhouse.json"
WHEELHOUSE_PREFIX: Final[str] = "wheels/"
_ZIP_TIMESTAMP: Final[tuple[int, int, int, int, int, int]] = (1980, 1, 1, 0, 0, 0)
_PYTHON_VERSION: Final[str] = "3.13"
_DOWNLOAD_TIMEOUT_SECONDS: Final[float] = 180.0


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
class RuntimeWheelhouse:
    """Validated wheelhouse archive paired with its strict manifest."""

    archive: Path
    manifest: dict[str, Any]


def _marker_environment(target: TargetPlatform) -> dict[str, str]:
    environment = dict(default_environment())
    environment.update(
        {
            "implementation_name": "cpython",
            "implementation_version": "3.13.0",
            "os_name": target.os_name,
            "platform_machine": target.platform_machine,
            "platform_python_implementation": "CPython",
            "platform_system": target.platform_system,
            "python_full_version": "3.13.0",
            "python_version": _PYTHON_VERSION,
            "sys_platform": target.sys_platform,
        }
    )
    return environment


def _interpreter_rank(tag: Tag) -> int | None:
    interpreter = tag.interpreter
    abi = tag.abi
    if interpreter in {"py3", "py313"} and abi == "none":
        return 0
    if interpreter == "cp313" and abi == "cp313":
        return 1
    if interpreter == "cp313" and abi == "abi3":
        return 2
    if interpreter.startswith("cp3") and interpreter[3:].isdigit() and abi == "abi3":
        minor = int(interpreter[3:])
        if minor <= 13:
            return 3 + (13 - minor)
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


def _wheel_rank(filename: str, target: TargetPlatform) -> tuple[int, int, int] | None:
    try:
        _name, _version, _build, tags = parse_wheel_filename(filename)
    except ValueError:
        return None
    ranks = []
    for tag in tags:
        interpreter_rank = _interpreter_rank(tag)
        platform_rank = _platform_rank(tag.platform, target)
        if interpreter_rank is not None and platform_rank is not None:
            ranks.append((0 if platform_rank == 0 else 1, interpreter_rank, -platform_rank))
    return min(ranks) if ranks else None


def _wheel_filename(url: str) -> str:
    filename = Path(urllib.parse.unquote(urllib.parse.urlparse(url).path)).name
    if not filename.endswith(".whl") or Path(filename).name != filename:
        raise SystemExit(f"lock wheel URL has an invalid filename: {url!r}")
    return filename


def _active_requirements(repo_root: Path, target: TargetPlatform) -> dict[str, Requirement]:
    environment = _marker_environment(target)
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


def plan_runtime_wheelhouse(repo_root: Path) -> tuple[dict[str, dict[str, str]], tuple[LockedWheel, ...]]:
    """Resolve the exact lock wheels required across every supported platform."""
    root = repo_root.resolve(strict=True)
    lock = tomllib.loads((root / "uv.lock").read_text(encoding=_UTF_8))
    by_name: dict[str, list[dict[str, Any]]] = {}
    for package in lock.get("package", []):
        if isinstance(package, dict) and isinstance(package.get("name"), str):
            by_name.setdefault(canonicalize_name(package["name"]), []).append(package)
    selected: dict[str, LockedWheel] = {}
    platforms: dict[str, dict[str, str]] = {}
    for target in SUPPORTED_TARGETS:
        target_rows: dict[str, str] = {}
        for name, requirement in sorted(_active_requirements(root, target).items()):
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
                rank = _wheel_rank(filename, target)
                if rank is not None:
                    wheels.append((rank, filename, url, digest.removeprefix("sha256:"), size))
            if not wheels:
                raise SystemExit(f"runtime lock has no {target.name} wheel for {requirement!s}")
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
    return platforms, tuple(selected[name] for name in sorted(selected))


def _manifest_document(repo_root: Path) -> tuple[dict[str, Any], tuple[LockedWheel, ...]]:
    platforms, wheels = plan_runtime_wheelhouse(repo_root)
    return (
        {
            "lock_sha256": sha256_path(repo_root / "uv.lock"),
            "platform_floors": PLATFORM_FLOORS,
            "platforms": platforms,
            "python": _PYTHON_VERSION,
            "schema": WHEELHOUSE_SCHEMA,
            "wheels": {
                wheel.filename: {
                    "distribution": wheel.distribution,
                    "sha256": wheel.sha256,
                    "size": wheel.size,
                    "version": wheel.version,
                }
                for wheel in wheels
            },
        },
        wheels,
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


def build_runtime_wheelhouse(repo_root: Path, destination: Path) -> RuntimeWheelhouse:
    """Download lock-selected wheels and write one deterministic sealed archive."""
    root = repo_root.resolve(strict=True)
    output = destination.resolve()
    if output.exists():
        raise FileExistsError(output)
    manifest, wheels = _manifest_document(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cadrumo-runtime-wheelhouse-") as temporary:
        wheel_dir = Path(temporary)
        for wheel in wheels:
            _download(wheel, wheel_dir / wheel.filename)
        with zipfile.ZipFile(output, mode="x", compression=zipfile.ZIP_STORED) as archive:
            manifest_info = zipfile.ZipInfo(WHEELHOUSE_MANIFEST, date_time=_ZIP_TIMESTAMP)
            manifest_info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(
                manifest_info,
                json.dumps(manifest, indent=2, sort_keys=True).encode(_UTF_8) + b"\n",
            )
            for wheel in wheels:
                info = zipfile.ZipInfo(f"{WHEELHOUSE_PREFIX}{wheel.filename}", date_time=_ZIP_TIMESTAMP)
                info.external_attr = (0o100644 & 0xFFFF) << 16
                archive.writestr(info, (wheel_dir / wheel.filename).read_bytes())
    return load_runtime_wheelhouse(output, expected_lock_sha256=manifest["lock_sha256"])


def load_runtime_wheelhouse(
    archive_path: Path,
    *,
    expected_lock_sha256: str | None = None,
) -> RuntimeWheelhouse:
    """Validate a closed wheelhouse archive and every declared wheel byte."""
    archive = archive_path.resolve(strict=True)
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if names.count(WHEELHOUSE_MANIFEST) != 1 or len(names) != len(set(names)):
            raise SystemExit("runtime wheelhouse has a missing or duplicate manifest/member")
        manifest = json.loads(bundle.read(WHEELHOUSE_MANIFEST))
        if not isinstance(manifest, dict) or set(manifest) != {
            "lock_sha256",
            "platform_floors",
            "platforms",
            "python",
            "schema",
            "wheels",
        }:
            raise SystemExit("runtime wheelhouse manifest schema drifted")
        if manifest.get("schema") != WHEELHOUSE_SCHEMA or manifest.get("python") != _PYTHON_VERSION:
            raise SystemExit("runtime wheelhouse identity drifted")
        if manifest.get("platform_floors") != PLATFORM_FLOORS:
            raise SystemExit("runtime wheelhouse platform support floor drifted")
        lock_sha256 = manifest.get("lock_sha256")
        if not isinstance(lock_sha256, str) or len(lock_sha256) != 64:
            raise SystemExit("runtime wheelhouse lock digest is invalid")
        if expected_lock_sha256 is not None and lock_sha256 != expected_lock_sha256:
            raise SystemExit("runtime wheelhouse does not bind the tested uv.lock")
        platforms = manifest.get("platforms")
        wheels = manifest.get("wheels")
        if not isinstance(platforms, dict) or set(platforms) != {target.name for target in SUPPORTED_TARGETS}:
            raise SystemExit("runtime wheelhouse platform closure is incomplete")
        if not isinstance(wheels, dict) or not wheels:
            raise SystemExit("runtime wheelhouse declares no wheels")
        declared = {WHEELHOUSE_MANIFEST, *(f"{WHEELHOUSE_PREFIX}{name}" for name in wheels)}
        if set(names) != declared:
            raise SystemExit("runtime wheelhouse member inventory drifted")
        for filename, raw in wheels.items():
            if not isinstance(filename, str) or Path(filename).name != filename or not isinstance(raw, dict):
                raise SystemExit("runtime wheelhouse wheel declaration is invalid")
            if set(raw) != {"distribution", "sha256", "size", "version"}:
                raise SystemExit(f"runtime wheelhouse wheel record drifted: {filename!r}")
            payload = bundle.read(f"{WHEELHOUSE_PREFIX}{filename}")
            if len(payload) != raw.get("size") or hashlib.sha256(payload).hexdigest() != raw.get("sha256"):
                raise SystemExit(f"runtime wheelhouse wheel bytes drifted: {filename!r}")
        for target, rows in platforms.items():
            if not isinstance(rows, dict) or not rows:
                raise SystemExit(f"runtime wheelhouse target closure is empty: {target!r}")
            for distribution, filename in rows.items():
                record = wheels.get(filename) if isinstance(filename, str) else None
                if not isinstance(distribution, str) or not isinstance(record, dict):
                    raise SystemExit(f"runtime wheelhouse target references an unknown wheel: {target!r}")
                if record.get("distribution") != distribution:
                    raise SystemExit(f"runtime wheelhouse target swaps distribution bytes: {target!r}/{distribution!r}")
    return RuntimeWheelhouse(archive=archive, manifest=manifest)


def extract_runtime_wheelhouse(archive_path: Path, destination: Path) -> RuntimeWheelhouse:
    """Validate then extract only declared wheel bytes into a new directory."""
    wheelhouse = load_runtime_wheelhouse(archive_path)
    target = destination.resolve()
    if target.exists():
        raise FileExistsError(target)
    target.mkdir(parents=True)
    wheels = wheelhouse.manifest["wheels"]
    with zipfile.ZipFile(wheelhouse.archive) as bundle:
        for filename in sorted(wheels):
            (target / filename).write_bytes(bundle.read(f"{WHEELHOUSE_PREFIX}{filename}"))
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
    "build_runtime_wheelhouse",
    "extract_runtime_wheelhouse",
    "load_runtime_wheelhouse",
    "plan_runtime_wheelhouse",
]
