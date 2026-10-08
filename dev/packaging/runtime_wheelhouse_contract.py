"""Typed runtime wheelhouse identities, support targets and archive format."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

WHEELHOUSE_SCHEMA: Final[str] = "cadrumo.runtime-wheelhouse.v3"
WHEELHOUSE_MANIFEST: Final[str] = "runtime-wheelhouse.json"
WHEELHOUSE_PREFIX: Final[str] = "wheels/"
_PYTHON_MINOR_RE: Final[re.Pattern[str]] = re.compile(r"^3\.(?P<minor>[0-9]+)$")


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


def target_platform(name: str) -> TargetPlatform:
    """Resolve a canonical target without consulting the build host."""
    for target in SUPPORTED_TARGETS:
        if target.name == name:
            return target
    raise ValueError(f"Unsupported distribution target: {name}")


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
