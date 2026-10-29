"""Validate the package's application environment declaration and compile its launch profiles."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from .environment_components import _components, _host_classes, _native_host, _temporary_member
from .environment_declaration_constants import (
    _BASE_NAME,
    _NAME,
    _SLOT,
    BASE_GROUPS,
    NAME_KINDS,
    NAME_ROLES,
    PATH_ENTRIES,
    PLATFORMS,
    SCHEMA,
)
from .environment_declaration_primitives import (
    DECLARATION,
    _fail,
    _keys,
    _list,
    _strings,
    _table,
)
from .environment_launch_vectors import _agent, _launch_vectors
from .environment_models import (
    ApplicationEnvironment,
    ExternalPathDefault,
    FixedValue,
    Invocation,
)
from .environment_path import _external_path_defaults
from .environment_profiles import _fixed, _invocations, _profiles
from .environment_root import _root, _vectors


def _names(raw: object) -> dict[str, dict[str, str]]:
    names: dict[str, dict[str, str]] = {}
    for name, entry in _table(raw, "names").items():
        if not _NAME.fullmatch(name):
            raise _fail(f"name is not an upper-case environment name: {name!r}")
        entry = _table(entry, f"names.{name}")
        _keys(entry, f"names.{name}", {"kind", "role"})
        if entry["kind"] not in NAME_KINDS:
            raise _fail(f"names.{name} has an undeclared kind {entry['kind']!r}")
        if entry["role"] not in NAME_ROLES:
            raise _fail(f"names.{name} has an undeclared role {entry['role']!r}")
        names[name] = {"kind": entry["kind"], "role": entry["role"]}
    return names


def _groups(raw: object, names: Mapping[str, Mapping[str, str]]) -> dict[str, tuple[str, ...]]:
    groups: dict[str, tuple[str, ...]] = {}
    for group, members in _table(raw, "groups").items():
        if not _SLOT.fullmatch(group):
            raise _fail(f"group name is malformed: {group!r}")
        groups[group] = _strings(members, f"groups.{group}", _NAME)
        for member in groups[group]:
            role = names.get(member, {}).get("role")
            if role not in {"location", "operator", "package"}:
                raise _fail(
                    f"groups.{group} admits {member}, which is not a declared operator, location or package name"
                )
    return groups


def _base(raw: object) -> dict[str, dict[str, tuple[str, ...]]]:
    table = _table(raw, "base")
    _keys(table, "base", set(PLATFORMS))
    base: dict[str, dict[str, tuple[str, ...]]] = {}
    for platform in PLATFORMS:
        groups = _table(table[platform], f"base.{platform}")
        _keys(groups, f"base.{platform}", set(BASE_GROUPS))
        base[platform] = _base_groups(groups, platform)
        listed = _base_names(base[platform], platform)
        if len(listed) != len(set(listed)):
            raise _fail(f"base.{platform} lists a name in more than one group")
        if platform == "windows" and any(name != name.upper() for name in listed):
            raise _fail("base.windows names must be upper case; Windows compares names without case")
    return base


def _base_groups(groups: dict[str, Any], platform: str) -> dict[str, tuple[str, ...]]:
    return {
        group: _strings(groups[group], f"base.{platform}.{group}", _BASE_NAME) if groups[group] else ()
        for group in BASE_GROUPS
    }


def _base_names(groups: dict[str, tuple[str, ...]], platform: str) -> list[str]:
    names = [name for group in groups.values() for name in group]
    return [name.upper() for name in names] if platform == "windows" else names


def parse(text: str) -> ApplicationEnvironment:
    """Validate the declaration's text against schema 1."""
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise _fail(f"is not valid TOML: {error}") from error
    _keys(
        document,
        "the declaration",
        {"schema", "names", "groups", "base", "pins", "path", "profiles", "host_classes", "native_host"}
        | {"components", "root"},
        {"invocations", "launch_vectors", "agent", "package_fixed"},
    )
    if document["schema"] != SCHEMA or isinstance(document["schema"], bool):
        raise _fail(f"schema must be {SCHEMA}")
    names = _names(document["names"])
    groups = _groups(document["groups"], names)
    base = _base(document["base"])
    pins = _table(document["pins"], "pins")
    _keys(pins, "pins", {"temporary", "temporary_member", "authority"})
    temporary = _strings(pins["temporary"], "pins.temporary", _NAME)
    if any(names.get(name, {}).get("role") != "pin" for name in temporary):
        raise _fail("pins.temporary must list declared pin names")
    authority = _fixed(pins["authority"], "pins.authority", names, role="fixed")
    if authority.source != "layout_path":
        raise _fail("pins.authority must name a layout path")
    temporary_member = _temporary_member(pins["temporary_member"], names)
    path, entries, external_path_defaults, windows_system, posix_system = _parse_path(document["path"], names, base)
    root_table = _table(document["root"], "root")
    root = _root(root_table, names)
    profiles = _profiles(document["profiles"], names, groups, root["variable"])
    package_fixed = tuple(
        _fixed(value, f"package_fixed[{index}]", names, role="fixed", allow_build_setting=True)
        for index, value in enumerate(_list(document.get("package_fixed", []), "package_fixed"))
    )
    _validate_package_fixed(package_fixed, profiles)
    _validate_agent_declaration(document, names, profiles)
    invocations = _invocations(document.get("invocations", []))
    native_host = _native_host(document["native_host"])
    _validate_profile_invocations(invocations, profiles)
    return ApplicationEnvironment(
        names=names,
        groups=groups,
        base=base,
        temporary=temporary,
        authority=authority,
        path_entries=entries,
        path_external=path["external"],
        external_path_defaults=external_path_defaults,
        windows_system=(
            windows_system["variable"],
            _strings(windows_system["subpaths"], "path.windows_system.subpaths"),
        ),
        posix_system=posix_system,
        profiles=profiles,
        invocations=invocations,
        temporary_member=temporary_member,
        host_classes=_host_classes(document["host_classes"]),
        native_host=native_host,
        components=_components(document["components"], names),
        root=root,
        vectors=_vectors(root_table.get("vectors"), root),
        launch_vectors=_launch_vectors(document.get("launch_vectors", []), profiles, native_host),
        package_fixed=package_fixed,
    )


def _validate_agent_declaration(
    document: dict[str, Any],
    names: Mapping[str, Mapping[str, str]],
    profiles: dict[str, dict[str, Any]],
) -> None:
    if "agent" in document:
        _agent(document["agent"], names, profiles)
    elif any(entry["agent_names"] for entry in profiles.values()):
        raise _fail("a profile admits the agent's names, and the declaration has no agent table")


def _parse_path(
    raw: object, names: Mapping[str, Mapping[str, str]], base: Mapping[str, Mapping[str, tuple[str, ...]]]
) -> tuple[dict[str, Any], tuple[str, ...], tuple[ExternalPathDefault, ...], dict[str, Any], tuple[str, ...]]:
    path = _table(raw, "path")
    _keys(path, "path", {"entries", "external", "windows_system", "posix_system"}, {"external_defaults"})
    entries = _strings(path["entries"], "path.entries")
    if not set(entries) <= PATH_ENTRIES or "executable" not in entries:
        raise _fail(f"path.entries must be drawn from {sorted(PATH_ENTRIES)} and include executable")
    if names.get(path["external"], {}).get("kind") != "directory_list":
        raise _fail("path.external must name a declared directory_list name")
    external_path_defaults = _external_path_defaults(path.get("external_defaults", []), base)
    windows_system = _table(path["windows_system"], "path.windows_system")
    _keys(windows_system, "path.windows_system", {"variable", "subpaths"})
    if not isinstance(windows_system["variable"], str) or not _BASE_NAME.fullmatch(windows_system["variable"]):
        raise _fail("path.windows_system.variable is malformed")
    if windows_system["variable"] not in base["windows"]["system"]:
        raise _fail("path.windows_system.variable must be a windows system base name")
    posix_system = _strings(path["posix_system"], "path.posix_system")
    if not all(entry.startswith("/") for entry in posix_system):
        raise _fail("path.posix_system entries must be absolute")
    return path, entries, external_path_defaults, windows_system, posix_system


def _validate_package_fixed(package_fixed: tuple[FixedValue, ...], profiles: dict[str, dict[str, Any]]) -> None:
    if any(value.source != "build_setting" for value in package_fixed):
        raise _fail("package_fixed must name build settings")
    package_names = {value.name for value in package_fixed}
    if len(package_names) != len(package_fixed):
        raise _fail("package_fixed repeats a name")
    for entry in profiles.values():
        if package_names & {
            *entry["operator"],
            *entry["pass"],
            *(slot.name for slot in entry["slots"]),
            *(value.name for value in entry["fixed"]),
        }:
            raise _fail("a profile cannot admit or override a package_fixed name")


def _validate_profile_invocations(invocations: tuple[Invocation, ...], profiles: dict[str, dict[str, Any]]) -> None:
    for invocation in invocations:
        if invocation.profile not in profiles:
            raise _fail(f"an invocation selects an undeclared profile {invocation.profile!r}")
    for profile, entry in profiles.items():
        invoked = any(invocation.profile == profile for invocation in invocations)
        entry["invoked"] = invoked
    _validate_invocation_patterns(invocations, profiles)


def _validate_invocation_patterns(invocations: tuple[Invocation, ...], profiles: dict[str, dict[str, Any]]) -> None:
    for image in {entry["image"] for entry in profiles.values()}:
        defaults = [name for name, entry in profiles.items() if entry["image"] == image and not entry["invoked"]]
        if len(defaults) > 1:
            raise _fail(f"image {image} has more than one profile without an invocation: {defaults}")
    _validate_platform_patterns(invocations, profiles)


def _validate_platform_patterns(invocations: tuple[Invocation, ...], profiles: dict[str, dict[str, Any]]) -> None:
    for platform in PLATFORMS:
        patterns = [
            (profiles[invocation.profile]["image"], invocation.arguments)
            for invocation in invocations
            if invocation.platform in {platform, "all"}
        ]
        if len(patterns) != len(set(patterns)):
            raise _fail(f"two invocations share one image and argument pattern on {platform}")


def load(root: Path, *, package_values: Mapping[str, str] | None = None) -> ApplicationEnvironment:
    """Read declaration metadata without consulting publisher provisioning."""
    declaration = parse((root / DECLARATION).read_text(encoding="utf-8"))
    return declaration if package_values is None else _with_package_values(declaration, package_values)


def _with_package_values(declaration: ApplicationEnvironment, values: Mapping[str, str]) -> ApplicationEnvironment:
    expected = {fixed.name for fixed in declaration.package_fixed}
    if set(values) != expected or any(not value or "\0" in value for value in values.values()):
        raise _fail("package-fixed build values are missing or invalid")
    vectors = tuple(
        {**vector, "environment": {**vector["environment"], **values}} if vector["refusal"] is None else vector
        for vector in declaration.launch_vectors
    )
    return replace(declaration, package_values=dict(values), launch_vectors=vectors)


def load_for_build(root: Path) -> ApplicationEnvironment:
    """Bind validated publisher provisioning for native contract generation."""
    return bind_build_provisioning(load(root), root)


def bind_build_provisioning(declaration: ApplicationEnvironment, root: Path) -> ApplicationEnvironment:
    """Resolve declared fixed inputs through their canonical build owners."""
    from ..google_oauth import GOOGLE_OAUTH_ENV, build_client_json

    values: dict[str, str] = {}
    for fixed in declaration.package_fixed:
        if fixed.value != GOOGLE_OAUTH_ENV:
            raise _fail("package_fixed names an unknown build setting")
        values[fixed.name] = build_client_json(root).get_secret_value()
    return _with_package_values(declaration, values)
