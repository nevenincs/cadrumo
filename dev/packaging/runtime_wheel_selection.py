"""Select exact lock-recorded wheels for every supported Python and platform."""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from packaging.requirements import Requirement
from packaging.tags import Tag
from packaging.utils import canonicalize_name, parse_wheel_filename

from cadrumo.core.toml import parse_toml

from .runtime_wheelhouse_contract import (
    SUPPORTED_TARGETS,
    LockedWheel,
    RuntimeWheelhousePlan,
    TargetPlatform,
    _canonical_python_minor,
    target_platform,
)
from .uv_constraints import export_runtime_constraints

_UTF_8 = "utf-8"


def _runtime_rows(repo_root: Path, python_versions: Sequence[str] | None) -> tuple[tuple[str, bool], ...]:
    """Return stable and advisory runtime rows from the canonical inventory."""
    if python_versions is not None:
        rows = tuple((_canonical_python_minor(value), True) for value in python_versions)
    else:
        from dev.ci.python_runtime_matrix import RuntimeMatrixError, load_runtime_inventory

        inventory_path = repo_root / "dev" / "ci" / "python-runtime-matrix.json"
        try:
            inventory = load_runtime_inventory(inventory_path)
        except RuntimeMatrixError as exc:
            raise SystemExit(f"runtime inventory cannot drive wheelhouse construction: {exc}") from exc
        rows = tuple((row.minor, row.blocking) for row in inventory.rows)
    if not rows:
        raise SystemExit("runtime wheelhouse runtime set is empty")
    if len({minor for minor, _blocking in rows}) != len(rows):
        raise SystemExit(f"runtime wheelhouse runtime set contains duplicates: {rows!r}")
    return rows


def marker_environment(target: TargetPlatform, python_version: str) -> dict[str, str]:
    """Project target markers; never inherit kernel or Python facts from the host."""
    python_minor = _canonical_python_minor(python_version)
    python_full_version = python_version if python_version.count(".") == 2 else f"{python_minor}.0"
    return {
        "implementation_name": "cpython",
        "implementation_version": python_full_version,
        "os_name": target.os_name,
        "platform_machine": target.platform_machine,
        "platform_python_implementation": "CPython",
        "platform_system": target.platform_system,
        "python_full_version": python_full_version,
        "python_version": python_minor,
        "sys_platform": target.sys_platform,
        "platform_release": "",
        "platform_version": "",
        "extra": "",
    }


def _stable_abi_rank(interpreter: str, abi: str, target_minor: int) -> int | None:
    if interpreter.startswith("cp3") and interpreter[3:].isdigit() and abi == "abi3":
        minor = int(interpreter[3:])
        if minor <= target_minor:
            return 3 + (target_minor - minor)
    return None


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
    return _stable_abi_rank(interpreter, abi, target_minor)


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
    filename = Path(unquote(urlparse(url).path)).name
    if not filename.endswith(".whl") or Path(filename).name != filename:
        raise SystemExit(f"lock wheel URL has an invalid filename: {url!r}")
    return filename


def active_requirements(repo_root: Path, target: TargetPlatform, python_version: str) -> dict[str, Requirement]:
    """Select the locked base closure with an explicit target marker environment."""
    environment = marker_environment(target, python_version)
    active: dict[str, Requirement] = {}
    for line in export_runtime_constraints(repo_root=repo_root):
        requirement = Requirement(line)
        if requirement.marker is not None and any(
            name in str(requirement.marker) for name in ("platform_release", "platform_version")
        ):
            raise ValueError(f"Target kernel marker has no declared value: {requirement}")
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


def _registry_package(name: str, requirement: Requirement, by_name: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
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
    return candidates[0]


def _ranked_lock_wheels(
    package: dict[str, Any], target: TargetPlatform, python_minor: str
) -> list[tuple[tuple[int, int, int], str, str, str, int]]:
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
    return wheels


def _selected_lock_wheel(
    name: str, package: dict[str, Any], wheels: list[tuple[tuple[int, int, int], str, str, str, int]]
) -> LockedWheel:
    # Compatibility is authoritative; filename breaks equivalent-tag ties.
    wheels.sort(key=lambda item: (item[0], item[1]))
    _rank, filename, url, digest, size = wheels[0]
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise SystemExit(f"runtime lock wheel digest is invalid for {filename!r}")
    return LockedWheel(
        distribution=name,
        version=str(package["version"]),
        filename=filename,
        url=url,
        sha256=digest,
        size=size,
    )


def _target_wheel_rows(
    root: Path,
    target: TargetPlatform,
    python_minor: str,
    by_name: dict[str, list[dict[str, Any]]],
    selected: dict[str, LockedWheel],
    missing: list[dict[str, str]],
) -> dict[str, str]:
    target_rows: dict[str, str] = {}
    for name, requirement in sorted(active_requirements(root, target, python_minor).items()):
        package = _registry_package(name, requirement, by_name)
        wheels = _ranked_lock_wheels(package, target, python_minor)
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
        wheel = _selected_lock_wheel(name, package, wheels)
        previous = selected.get(wheel.filename)
        if previous is not None and previous != wheel:
            raise SystemExit(f"runtime lock assigns conflicting bytes to {wheel.filename!r}")
        selected[wheel.filename] = wheel
        target_rows[name] = wheel.filename
    return target_rows


def _plan_runtime_wheelhouse(
    repo_root: Path, python_version: str, targets: Sequence[TargetPlatform] = SUPPORTED_TARGETS
) -> RuntimeWheelhousePlan:
    """Resolve one runtime's exact lock wheels across every supported platform."""
    root = repo_root.resolve(strict=True)
    python_minor = _canonical_python_minor(python_version)
    lock = parse_toml((root / "uv.lock").read_text(encoding=_UTF_8))
    by_name: dict[str, list[dict[str, Any]]] = {}
    for package in lock.get("package", []):
        if isinstance(package, dict) and isinstance(package.get("name"), str):
            by_name.setdefault(canonicalize_name(package["name"]), []).append(package)
    selected: dict[str, LockedWheel] = {}
    platforms: dict[str, dict[str, str]] = {}
    missing: list[dict[str, str]] = []
    for target in targets:
        platforms[target.name] = _target_wheel_rows(root, target, python_version, by_name, selected, missing)
    return RuntimeWheelhousePlan(
        python_version=python_minor,
        platforms=platforms,
        wheels=tuple(selected[name] for name in sorted(selected)),
        missing=tuple(missing),
    )


def _missing_wheel_message(plan: RuntimeWheelhousePlan) -> str:
    missing = "; ".join(f"{item['distribution']} ({item['platform']}, {item['requirement']})" for item in plan.missing)
    return f"runtime lock has no complete {plan.python_version} wheelhouse: {missing}"


def plan_target_wheels(repo_root: Path, target: str, python_version: str) -> tuple[LockedWheel, ...]:
    """Select one target's hash-pinned wheels using the existing floor/ABI rules."""
    plan = _plan_runtime_wheelhouse(repo_root, python_version, (target_platform(target),))
    if plan.missing:
        raise SystemExit(_missing_wheel_message(plan))
    return plan.wheels


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
