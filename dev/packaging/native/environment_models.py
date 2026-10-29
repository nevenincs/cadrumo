"""Typed values of the validated application environment declaration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FixedValue:
    """A package fact a profile sets: a literal, a package-relative path or a declared image's path."""

    name: str
    source: str
    value: str


@dataclass(frozen=True)
class LaunchSlot:
    """A launch parameter a parent supplies within a declared name and kind."""

    name: str
    kind: str
    required: bool


@dataclass(frozen=True)
class ExternalPathDefault:
    """A declaration-owned installation directory considered for an admitted image's PATH."""

    platform: str
    variable: str | None
    path: str
    subpaths: tuple[str, ...]


@dataclass(frozen=True)
class LaunchProfile:
    """One image's compiled environment definition."""

    name: str
    image: str
    inherit: bool
    base: tuple[str, ...]
    pins: tuple[str, ...]
    operator: tuple[str, ...]
    passed: tuple[str, ...]
    fixed: tuple[FixedValue, ...]
    slots: tuple[LaunchSlot, ...]
    package_path: bool
    invoked: bool


@dataclass(frozen=True)
class InvocationArgument:
    """One position of an invocation: an exact literal, a typed value or an optional flag with a typed value."""

    literal: str | None
    slot: str | None
    kind: str | None
    minimum: int
    option: str | None = None


@dataclass(frozen=True)
class Invocation:
    """An exact argument pattern that selects a profile on one platform family."""

    profile: str
    platform: str
    arguments: tuple[InvocationArgument, ...]
    distinct: tuple[tuple[str, str], ...]
    greater: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ApplicationEnvironment:
    """The validated declaration, independent of a build target."""

    names: Mapping[str, Mapping[str, str]]
    groups: Mapping[str, tuple[str, ...]]
    base: Mapping[str, Mapping[str, tuple[str, ...]]]
    temporary: tuple[str, ...]
    authority: FixedValue
    path_entries: tuple[str, ...]
    path_external: str
    external_path_defaults: tuple[ExternalPathDefault, ...]
    windows_system: tuple[str, tuple[str, ...]]
    posix_system: tuple[str, ...]
    profiles: Mapping[str, dict[str, Any]]
    invocations: tuple[Invocation, ...]
    temporary_member: Mapping[str, Any]
    host_classes: Mapping[str, Any]
    native_host: Mapping[str, Any]
    components: Mapping[str, Any]
    root: Mapping[str, Any]
    vectors: tuple[Mapping[str, Any], ...]
    launch_vectors: tuple[Mapping[str, Any], ...]
    package_fixed: tuple[FixedValue, ...] = ()
    package_values: Mapping[str, str] = field(default_factory=dict)
