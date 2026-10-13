"""Validate the package's application environment declaration and compile its launch profiles."""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath
from typing import Any

DECLARATION = Path("native/application-environment.toml")
SCHEMA = 1

NAME_KINDS = frozenset(
    {
        "text",
        "language",
        "boolean",
        "integer",
        "number",
        "directory",
        "file",
        "directory_list",
        "port",
        "executable",
        "descriptor",
    }
)
NAME_ROLES = frozenset({"location", "operator", "package", "pin", "fixed", "slot", "pass"})
ARGUMENT_KINDS = frozenset({"handle", "descriptor"})
BASE_GROUPS = ("system", "session", "terminal", "display", "network")
PLATFORMS = ("windows", "posix")
PATH_ENTRIES = frozenset({"executable", "external", "native", "system"})

# Declared names reach C and Rust string literals and process environments unescaped.
_NAME = re.compile(r"[A-Z][A-Z0-9_]*")
# Operating-system names keep their platform spelling, such as PROGRAMFILES(X86) or http_proxy.
_BASE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\([A-Za-z0-9]+\))?")
_PROFILE = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*")
_SLOT = re.compile(r"[a-z][a-z0-9_]*")
# Literal arguments become C and Rust string literals; keep them printable ASCII without quotes.
_LITERAL = re.compile(r"[A-Za-z0-9_.:/=+-]+")


class ApplicationEnvironmentError(ValueError):
    """The declaration violates its schema; generation stops."""


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
class LaunchProfile:
    """One image's compiled environment definition."""

    name: str
    image: str
    inherit: bool
    base: tuple[str, ...]
    pins: bool
    operator: tuple[str, ...]
    passed: tuple[str, ...]
    fixed: tuple[FixedValue, ...]
    slots: tuple[LaunchSlot, ...]
    package_path: bool
    invoked: bool


@dataclass(frozen=True)
class InvocationArgument:
    """One position of an invocation: an exact literal or a typed value."""

    literal: str | None
    slot: str | None
    kind: str | None
    minimum: int


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
    windows_system: tuple[str, tuple[str, ...]]
    posix_system: tuple[str, ...]
    profiles: Mapping[str, Mapping[str, Any]]
    invocations: tuple[Invocation, ...]
    temporary_member: Mapping[str, Any]
    host_classes: Mapping[str, Any]
    native_host: Mapping[str, Any]
    components: Mapping[str, Any]
    root: Mapping[str, Any]
    vectors: tuple[Mapping[str, Any], ...]
    launch_vectors: tuple[Mapping[str, Any], ...]


def _fail(message: str) -> ApplicationEnvironmentError:
    return ApplicationEnvironmentError(f"{DECLARATION.as_posix()}: {message}")


def _table(value: object, where: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(f"{where} must be a table")
    return value


def _strings(value: object, where: str, pattern: re.Pattern[str] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise _fail(f"{where} must be a list of non-empty strings")
    if pattern is not None:
        for item in value:
            if not pattern.fullmatch(item):
                raise _fail(f"{where} has a malformed entry: {item!r}")
    items = tuple(str(item) for item in value)
    if len(set(items)) != len(items):
        raise _fail(f"{where} repeats an entry")
    return items


def _keys(
    table: Mapping[str, Any], where: str, required: set[str], optional: frozenset[str] | set[str] = frozenset()
) -> None:
    missing, unknown = required - set(table), set(table) - required - optional
    if missing or unknown:
        raise _fail(f"{where} must declare {sorted(required)}; missing {sorted(missing)}, unknown {sorted(unknown)}")


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
        base[platform] = {
            group: _strings(groups[group], f"base.{platform}.{group}", _BASE_NAME) if groups[group] else ()
            for group in BASE_GROUPS
        }
        listed = [
            name.upper() if platform == "windows" else name for group in base[platform].values() for name in group
        ]
        if len(listed) != len(set(listed)):
            raise _fail(f"base.{platform} lists a name in more than one group")
        if platform == "windows" and any(name != name.upper() for name in listed):
            raise _fail("base.windows names must be upper case; Windows compares names without case")
    return base


def _argument(raw: object, where: str) -> InvocationArgument:
    entry = _table(raw, where)
    if "literal" in entry:
        _keys(entry, where, {"literal"})
        if not isinstance(entry["literal"], str) or not _LITERAL.fullmatch(entry["literal"]):
            raise _fail(f"{where} literal is malformed")
        return InvocationArgument(literal=entry["literal"], slot=None, kind=None, minimum=0)
    _keys(entry, where, {"slot", "kind"}, {"minimum"})
    if not isinstance(entry["slot"], str) or not _SLOT.fullmatch(entry["slot"]):
        raise _fail(f"{where} slot is malformed")
    if entry["kind"] not in ARGUMENT_KINDS:
        raise _fail(f"{where} has an undeclared argument kind {entry['kind']!r}")
    minimum = entry.get("minimum", 1)
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        raise _fail(f"{where} minimum must be a positive integer")
    return InvocationArgument(literal=None, slot=entry["slot"], kind=entry["kind"], minimum=minimum)


def _pairs(raw: object, where: str, slots: set[str]) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, list):
        raise _fail(f"{where} must be a list of slot pairs")
    pairs: list[tuple[str, str]] = []
    for pair in raw:
        if not isinstance(pair, list) or len(pair) != 2 or not set(pair) <= slots or pair[0] == pair[1]:
            raise _fail(f"{where} must pair two distinct declared argument slots: {pair!r}")
        pairs.append((pair[0], pair[1]))
    return tuple(pairs)


def _invocations(raw: object) -> tuple[Invocation, ...]:
    if not isinstance(raw, list):
        raise _fail("invocations must be an array of tables")
    invocations: list[Invocation] = []
    for index, item in enumerate(raw):
        where = f"invocations[{index}]"
        entry = _table(item, where)
        _keys(entry, where, {"profile", "platform", "arguments"}, {"distinct", "greater"})
        if entry["platform"] not in {*PLATFORMS, "all"}:
            raise _fail(f"{where} platform must be windows, posix or all")
        if not isinstance(entry["arguments"], list) or not entry["arguments"]:
            raise _fail(f"{where} must declare at least one argument")
        arguments = tuple(
            _argument(argument, f"{where}.arguments[{i}]") for i, argument in enumerate(entry["arguments"])
        )
        if arguments[0].literal is None:
            raise _fail(f"{where} must start with a literal argument")
        slots = [argument.slot for argument in arguments if argument.slot is not None]
        if len(slots) != len(set(slots)):
            raise _fail(f"{where} repeats an argument slot")
        invocations.append(
            Invocation(
                profile=str(entry["profile"]),
                platform=entry["platform"],
                arguments=arguments,
                distinct=_pairs(entry.get("distinct", []), f"{where}.distinct", set(slots)),
                greater=_pairs(entry.get("greater", []), f"{where}.greater", set(slots)),
            )
        )
    return tuple(invocations)


def _fixed(raw: object, where: str, names: Mapping[str, Mapping[str, str]], *, role: str) -> FixedValue:
    entry = _table(raw, where)
    sources = {"value", "layout_path", "image"} & set(entry)
    if len(sources) != 1:
        raise _fail(f"{where} must declare exactly one of value, layout_path or image")
    _keys(entry, where, {"name", *sources})
    name, source = entry["name"], next(iter(sources))
    if names.get(name, {}).get("role") != role:
        raise _fail(f"{where} sets {name!r}, which is not a declared {role} name")
    if not isinstance(entry[source], str) or not entry[source]:
        raise _fail(f"{where} {source} must be a non-empty string")
    return FixedValue(name=name, source=source, value=entry[source])


def _profiles(
    raw: object, names: Mapping[str, Mapping[str, str]], groups: Mapping[str, tuple[str, ...]]
) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for profile, item in _table(raw, "profiles").items():
        where = f"profiles.{profile}"
        if not _PROFILE.fullmatch(profile):
            raise _fail(f"profile name is not a lowercase hyphenated identifier: {profile!r}")
        entry = _table(item, where)
        _keys(entry, where, {"image", "base", "pins", "path"}, {"base_groups", "operator", "pass", "fixed", "slots"})
        if not isinstance(entry["image"], str) or not _PROFILE.fullmatch(entry["image"]):
            raise _fail(f"{where} image is malformed")
        if entry["base"] not in {"groups", "inherit"} or entry["path"] not in {"package", "inherit"}:
            raise _fail(f"{where} base must be groups or inherit and path must be package or inherit")
        if not isinstance(entry["pins"], bool):
            raise _fail(f"{where} pins must be a boolean")
        inherit = entry["base"] == "inherit"
        if inherit and (entry["pins"] or entry["path"] != "inherit" or set(entry) - {"image", "base", "pins", "path"}):
            raise _fail(f"{where} inherits its caller's environment and may not pin, project or admit names")
        base_groups = _strings(entry.get("base_groups", []), f"{where}.base_groups") if not inherit else ()
        if not inherit and not base_groups:
            raise _fail(f"{where} must name its base groups")
        if not set(base_groups) <= set(BASE_GROUPS):
            raise _fail(f"{where}.base_groups names an undeclared base group")
        operator_groups = _strings(entry.get("operator", []), f"{where}.operator")
        if not set(operator_groups) <= set(groups):
            raise _fail(f"{where}.operator names an undeclared group")
        operator = tuple(name for group in operator_groups for name in groups[group])
        passed = _strings(entry.get("pass", []), f"{where}.pass", _NAME)
        for name in passed:
            if name not in names:
                raise _fail(f"{where}.pass admits an undeclared name {name}")
        fixed = tuple(
            _fixed(value, f"{where}.fixed[{index}]", names, role="fixed")
            for index, value in enumerate(_list(entry.get("fixed", []), f"{where}.fixed"))
        )
        slots: list[LaunchSlot] = []
        for index, value in enumerate(_list(entry.get("slots", []), f"{where}.slots")):
            slot = _table(value, f"{where}.slots[{index}]")
            _keys(slot, f"{where}.slots[{index}]", {"name", "required"})
            name = slot["name"]
            if names.get(name, {}).get("role") != "slot" or not isinstance(slot["required"], bool):
                raise _fail(f"{where}.slots[{index}] must name a declared slot and whether it is required")
            slots.append(LaunchSlot(name=name, kind=names[name]["kind"], required=slot["required"]))
        defined = [*operator, *passed, *(value.name for value in fixed), *(slot.name for slot in slots)]
        if len(defined) != len(set(defined)):
            raise _fail(f"{where} admits or sets one name twice")
        profiles[profile] = {
            "image": entry["image"],
            "inherit": inherit,
            "base_groups": base_groups,
            "pins": entry["pins"],
            "operator": operator,
            "pass": passed,
            "fixed": fixed,
            "slots": tuple(slots),
            "package_path": entry["path"] == "package",
        }
    return profiles


def _list(value: object, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise _fail(f"{where} must be a list")
    return value


def _relative(value: object, where: str) -> str:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\" in value:
        raise _fail(f"{where} must be a relative path with forward slashes")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise _fail(f"{where} must not hold empty, current or parent components")
    return value


def _integer(value: object, where: str, *, minimum: int = 1) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise _fail(f"{where} must be an integer of at least {minimum}")
    return value


def _temporary_member(raw: object, names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    entry = _table(raw, "pins.temporary_member")
    _keys(entry, "pins.temporary_member", {"name", "default", "create_explicit"})
    if names.get(entry["name"], {}).get("role") != "location":
        raise _fail("pins.temporary_member must name a declared location")
    if not isinstance(entry["create_explicit"], bool):
        raise _fail("pins.temporary_member.create_explicit must be a boolean")
    return {
        "name": entry["name"],
        "default": _relative(entry["default"], "pins.temporary_member.default"),
        "create_explicit": entry["create_explicit"],
    }


def _host_classes(raw: object) -> dict[str, Any]:
    entry = _table(raw, "host_classes")
    _keys(entry, "host_classes", {"cleared_prefixes", "cleared_names", "namespace_prefix"})
    prefix = entry["namespace_prefix"]
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*_", prefix):
        raise _fail("host_classes.namespace_prefix must be an upper-case prefix ending in an underscore")
    return {
        "cleared_prefixes": list(_strings(entry["cleared_prefixes"], "host_classes.cleared_prefixes", _BASE_NAME)),
        "cleared_names": list(_strings(entry["cleared_names"], "host_classes.cleared_names", _BASE_NAME)),
        "namespace_prefix": prefix,
    }


def _native_host(raw: object) -> dict[str, Any]:
    entry = _table(raw, "native_host")
    _keys(entry, "native_host", {"owner", "first", "last", "launch_profile_refused", "refusals"})
    if not isinstance(entry["owner"], str) or not _SLOT.fullmatch(entry["owner"]):
        raise _fail("native_host.owner must be a lower-case token")
    first = _integer(entry["first"], "native_host.first")
    last = _integer(entry["last"], "native_host.last", minimum=first)
    refused = _integer(entry["launch_profile_refused"], "native_host.launch_profile_refused")
    # POSIX reports only the low byte of an exit status.
    if last > 0xFF or not first <= refused <= last:
        raise _fail("native_host exit codes must lie in one byte and hold launch_profile_refused")
    return {
        "owner": entry["owner"],
        "first": first,
        "last": last,
        "launch_profile_refused": refused,
        "refusals": list(_strings(entry["refusals"], "native_host.refusals", _SLOT)),
    }


_COMPONENT_PATHS = (
    "console_workspace",
    "webview",
    "manager_log_file",
    "manager_preferences",
    "manager_failed_versions",
    "logs",
    "log_file",
)
_COMPONENT_VALUES = (
    "log_variable",
    "log_format",
    "log_max_bytes",
    "log_backups",
    "language_variable",
    "language_default",
)


def _components(raw: object, names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    entry = _table(raw, "components")
    _keys(entry, "components", {*_COMPONENT_PATHS, *_COMPONENT_VALUES})
    components: dict[str, Any] = {key: _relative(entry[key], f"components.{key}") for key in _COMPONENT_PATHS}
    if not components["log_file"].startswith(components["logs"] + "/"):
        raise _fail("components.log_file must lie in components.logs")
    if names.get(entry["log_variable"], {}).get("role") != "location":
        raise _fail("components.log_variable must name a declared location")
    if not isinstance(entry["log_format"], str) or not entry["log_format"]:
        raise _fail("components.log_format must be a non-empty string")
    if names.get(entry["language_variable"], {}).get("kind") != "language":
        raise _fail("components.language_variable must name a declared language name")
    language = entry["language_default"]
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}", language):
        raise _fail("components.language_default must be a two-letter lower-case language")
    components.update(
        log_variable=entry["log_variable"],
        log_format=entry["log_format"],
        log_max_bytes=_integer(entry["log_max_bytes"], "components.log_max_bytes"),
        log_backups=_integer(entry["log_backups"], "components.log_backups", minimum=0),
        language_variable=entry["language_variable"],
        language_default=language,
    )
    return components


ROOT_PLATFORMS = ("windows", "linux", "macos")
ROOT_MODES = ("development", "installed")
_PATH_RULES = ("unicode_required", "normalize_absolute", "refuse_links", "enforce_existing_permissions")
_ROOT_KEYS = {
    "variable",
    "development_variable",
    "checkout_marker",
    "development_default",
    "precedence",
    "relative_override",
    "posix_directory_mode",
    "refusals",
    "path_rules",
    "channel",
    "installed_defaults",
}


def _installed_default(raw: object, where: str) -> dict[str, Any]:
    rule = _table(raw, where)
    _keys(rule, where, {"platform", "candidates", "home_variable"})
    candidates = []
    for position, item in enumerate(_list(rule["candidates"], f"{where}.candidates")):
        candidate = _table(item, f"{where}.candidates[{position}]")
        _keys(candidate, f"{where}.candidates[{position}]", {"variable", "subpath"})
        if not isinstance(candidate["variable"], str) or not _BASE_NAME.fullmatch(candidate["variable"]):
            raise _fail(f"{where}.candidates[{position}].variable is malformed")
        subpath = (
            _strings(candidate["subpath"], f"{where}.candidates[{position}].subpath") if candidate["subpath"] else ()
        )
        candidates.append({"variable": candidate["variable"], "subpath": list(subpath)})
    home = rule["home_variable"]
    if not candidates or not isinstance(home, str) or not _BASE_NAME.fullmatch(home):
        raise _fail(f"{where} needs base candidates and a home variable")
    return {"platform": rule["platform"], "candidates": candidates, "home_variable": home}


def _root(entry: Mapping[str, Any], names: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    _keys(entry, "root", _ROOT_KEYS, {"vectors"})
    variable, development = entry["variable"], entry["development_variable"]
    if names.get(variable, {}).get("role") != "location":
        raise _fail("root.variable must name a declared location")
    if not isinstance(development, str) or not _NAME.fullmatch(development) or development in names:
        raise _fail("root.development_variable must be an environment name no profile admits")
    precedence = _table(entry["precedence"], "root.precedence")
    _keys(precedence, "root.precedence", set(ROOT_MODES))
    ordered = _strings(precedence["development"], "root.precedence.development")
    if precedence["installed"] != [variable] or ordered[0] != variable or not set(ordered) <= {variable, development}:
        raise _fail("root.precedence must put root.variable first and alone when installed")
    relative = _table(entry["relative_override"], "root.relative_override")
    _keys(relative, "root.relative_override", set(ROOT_MODES))
    if not {relative["development"], relative["installed"]} <= {"anchor_at_checkout", "refuse"}:
        raise _fail("root.relative_override values must be anchor_at_checkout or refuse")
    mode = _integer(entry["posix_directory_mode"], "root.posix_directory_mode")
    if mode > 0o777:
        raise _fail("root.posix_directory_mode must be a permission mode")
    rules = _table(entry["path_rules"], "root.path_rules")
    _keys(rules, "root.path_rules", set(_PATH_RULES))
    if not all(isinstance(rules[rule], bool) for rule in _PATH_RULES):
        raise _fail("root.path_rules values must be booleans")
    channel = _table(entry["channel"], "root.channel")
    _keys(channel, "root.channel", {"product_directory", "stable", "separator"})
    if not all(isinstance(value, str) and re.fullmatch(r"[a-z0-9-]+", value) for value in channel.values()):
        raise _fail("root.channel values must be lower-case tokens")
    defaults = [
        _installed_default(item, f"root.installed_defaults[{index}]")
        for index, item in enumerate(_list(entry["installed_defaults"], "root.installed_defaults"))
    ]
    if [rule["platform"] for rule in defaults] != list(ROOT_PLATFORMS):
        raise _fail(f"root.installed_defaults must declare {list(ROOT_PLATFORMS)} in order")
    return {
        "variable": variable,
        "development_variable": development,
        "checkout_marker": _relative(entry["checkout_marker"], "root.checkout_marker"),
        "precedence": {"development": list(ordered), "installed": [variable]},
        "development_default": _relative(entry["development_default"], "root.development_default"),
        "installed_defaults": defaults,
        "channel": {key: channel[key] for key in ("product_directory", "stable", "separator")},
        "relative_override": {mode_name: relative[mode_name] for mode_name in ROOT_MODES},
        "blank_is_unset": True,
        "posix_directory_mode": mode,
        "refusals": list(_strings(entry["refusals"], "root.refusals", _SLOT)),
        "path_rules": {rule: rules[rule] for rule in _PATH_RULES},
    }


_VECTOR_OPTIONAL = frozenset(
    {
        "checkout",
        "known_folder",
        "channel",
        "root",
        "refusal",
        "invalid_environment",
        "invalid_checkout",
        "invalid_known_folder",
    }
)


def _vector(raw: object, where: str, root: Mapping[str, Any]) -> dict[str, Any]:
    entry = _table(raw, where)
    _keys(entry, where, {"name", "platform", "mode", "environment"}, _VECTOR_OPTIONAL)
    if entry["platform"] not in ROOT_PLATFORMS or entry["mode"] not in ROOT_MODES:
        raise _fail(f"{where} names an undeclared platform or mode")
    if ("root" in entry) == ("refusal" in entry):
        raise _fail(f"{where} must declare exactly one of root and refusal")
    if "refusal" in entry and entry["refusal"] not in root["refusals"]:
        raise _fail(f"{where} names an undeclared refusal")
    environment = _table(entry["environment"], f"{where}.environment")
    optional = {key: entry.get(key) for key in ("checkout", "known_folder", "root", "refusal")}
    if not all(isinstance(value, str) for value in (*environment.values(), *(v for v in optional.values() if v))):
        raise _fail(f"{where} values must be strings")
    flags = {key: entry.get(key, False) for key in ("invalid_checkout", "invalid_known_folder")}
    if not all(isinstance(value, bool) for value in flags.values()):
        raise _fail(f"{where} flags must be booleans")
    invalid = (
        _strings(entry["invalid_environment"], f"{where}.invalid_environment") if "invalid_environment" in entry else ()
    )
    return {
        "name": str(entry["name"]),
        "platform": entry["platform"],
        "mode": entry["mode"],
        "environment": dict(sorted(environment.items())),
        "checkout": optional["checkout"],
        "known_folder": optional["known_folder"],
        "channel": str(entry.get("channel", root["channel"]["stable"])),
        "expected_root": optional["root"],
        "refusal": optional["refusal"],
        "invalid_environment": list(invalid),
        **flags,
    }


def _vectors(raw: object, root: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    vectors = tuple(
        _vector(item, f"root.vectors[{index}]", root)
        for index, item in enumerate(_list([] if raw is None else raw, "root.vectors"))
    )
    if len({vector["name"] for vector in vectors}) != len(vectors):
        raise _fail("root.vectors repeats a vector name")
    return vectors


def channel_directory(root: Mapping[str, Any], channel: str) -> str:
    """Name the per-channel root directory; the stable channel uses the bare product directory."""
    names = root["channel"]
    if channel == names["stable"]:
        return str(names["product_directory"])
    return f"{names['product_directory']}{names['separator']}{channel}"


def _agent(raw: object, names: Mapping[str, Mapping[str, str]], profiles: Mapping[str, Mapping[str, Any]]) -> None:
    """Hold the agent's names to the agent image: no other profile admits or sets them."""
    entry = _table(raw, "agent")
    _keys(entry, "agent", {"image", "prefix", "hosting_contract", "never_admitted"})
    image, prefix = entry["image"], entry["prefix"]
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Z][A-Z0-9]*(_[A-Z0-9]+)*_", prefix):
        raise _fail("agent.prefix must be an upper-case prefix ending in an underscore")
    _integer(entry["hosting_contract"], "agent.hosting_contract")
    never = _strings(entry["never_admitted"], "agent.never_admitted", _NAME)
    if not all(name.startswith(prefix) for name in never) or set(never) & set(names):
        raise _fail("agent.never_admitted names carry the agent prefix and are declared nowhere")
    for profile, declared in profiles.items():
        spelled = [*declared["operator"], *declared["pass"], *(slot.name for slot in declared["slots"])]
        spelled += [value.name for value in declared["fixed"]]
        if declared["image"] != image and any(name.startswith(prefix) for name in spelled):
            raise _fail(f"profiles.{profile} admits an agent name outside the {image} image")


def _text_table(raw: object, where: str) -> dict[str, str]:
    table = _table(raw, where)
    if not all(isinstance(value, str) for value in table.values()):
        raise _fail(f"{where} values must be strings")
    return {str(key): str(value) for key, value in table.items()}


def _launch_vector(
    raw: object, where: str, profiles: Mapping[str, Mapping[str, Any]], native_host: Mapping[str, Any]
) -> dict[str, Any]:
    entry = _table(raw, where)
    _keys(
        entry,
        where,
        {"name", "platform", "image", "arguments", "ambient"},
        {"profile", "environment", "path", "refusal"},
    )
    if entry["platform"] not in PLATFORMS:
        raise _fail(f"{where} platform must be windows or posix")
    arguments = _list(entry["arguments"], f"{where}.arguments")
    if not all(isinstance(argument, str) for argument in arguments):
        raise _fail(f"{where}.arguments must be strings")
    if ("refusal" in entry) == ("profile" in entry) or ("refusal" in entry and ({"environment", "path"} & set(entry))):
        raise _fail(f"{where} must declare either a profile and its environment or a refusal")
    vector: dict[str, Any] = {
        "name": str(entry["name"]),
        "platform": entry["platform"],
        "image": str(entry["image"]),
        "arguments": [str(argument) for argument in arguments],
        "ambient": _text_table(entry["ambient"], f"{where}.ambient"),
        "profile": None,
        "environment": {},
        "path": None,
        "refusal": None,
    }
    if "refusal" in entry:
        refusal = _text_table(entry["refusal"], f"{where}.refusal")
        _keys(refusal, f"{where}.refusal", {"code", "subject"})
        if refusal["code"] not in native_host["refusals"]:
            raise _fail(f"{where} names an undeclared refusal")
        vector["refusal"] = {"code": refusal["code"], "subject": refusal["subject"]}
        return vector
    if entry["profile"] not in profiles:
        raise _fail(f"{where} selects an undeclared profile")
    vector["profile"] = entry["profile"]
    vector["environment"] = _text_table(entry.get("environment", {}), f"{where}.environment")
    if "path" in entry:
        vector["path"] = list(_strings(entry["path"], f"{where}.path"))
    return vector


def _launch_vectors(
    raw: object, profiles: Mapping[str, Mapping[str, Any]], native_host: Mapping[str, Any]
) -> tuple[dict[str, Any], ...]:
    vectors = tuple(
        _launch_vector(item, f"launch_vectors[{index}]", profiles, native_host)
        for index, item in enumerate(_list(raw, "launch_vectors"))
    )
    if len({vector["name"] for vector in vectors}) != len(vectors):
        raise _fail("launch_vectors repeats a vector name")
    return vectors


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
        {"invocations", "launch_vectors", "agent"},
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
    path = _table(document["path"], "path")
    _keys(path, "path", {"entries", "external", "windows_system", "posix_system"})
    entries = _strings(path["entries"], "path.entries")
    if not set(entries) <= PATH_ENTRIES or "executable" not in entries:
        raise _fail(f"path.entries must be drawn from {sorted(PATH_ENTRIES)} and include executable")
    if names.get(path["external"], {}).get("kind") != "directory_list":
        raise _fail("path.external must name a declared directory_list name")
    windows_system = _table(path["windows_system"], "path.windows_system")
    _keys(windows_system, "path.windows_system", {"variable", "subpaths"})
    if not isinstance(windows_system["variable"], str) or not _BASE_NAME.fullmatch(windows_system["variable"]):
        raise _fail("path.windows_system.variable is malformed")
    if windows_system["variable"] not in base["windows"]["system"]:
        raise _fail("path.windows_system.variable must be a windows system base name")
    posix_system = _strings(path["posix_system"], "path.posix_system")
    if not all(entry.startswith("/") for entry in posix_system):
        raise _fail("path.posix_system entries must be absolute")
    root_table = _table(document["root"], "root")
    root = _root(root_table, names)
    profiles = _profiles(document["profiles"], names, groups)
    if "agent" in document:
        _agent(document["agent"], names, profiles)
    invocations = _invocations(document.get("invocations", []))
    native_host = _native_host(document["native_host"])
    for invocation in invocations:
        if invocation.profile not in profiles:
            raise _fail(f"an invocation selects an undeclared profile {invocation.profile!r}")
    for profile, entry in profiles.items():
        invoked = any(invocation.profile == profile for invocation in invocations)
        entry["invoked"] = invoked
    for image in {entry["image"] for entry in profiles.values()}:
        defaults = [name for name, entry in profiles.items() if entry["image"] == image and not entry["invoked"]]
        if len(defaults) > 1:
            raise _fail(f"image {image} has more than one profile without an invocation: {defaults}")
    for platform in PLATFORMS:
        patterns = [
            (profiles[invocation.profile]["image"], invocation.arguments)
            for invocation in invocations
            if invocation.platform in {platform, "all"}
        ]
        if len(patterns) != len(set(patterns)):
            raise _fail(f"two invocations share one image and argument pattern on {platform}")
    return ApplicationEnvironment(
        names=names,
        groups=groups,
        base=base,
        temporary=temporary,
        authority=authority,
        path_entries=entries,
        path_external=path["external"],
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
    )


def load(root: Path) -> ApplicationEnvironment:
    """Read and validate the declaration from a source tree."""
    return parse((root / DECLARATION).read_text(encoding="utf-8"))


def _platform_family(layout: Mapping[str, Any]) -> str:
    return "windows" if layout["backend"] == "windows" else "posix"


def images(layout: Mapping[str, Any]) -> tuple[str, ...]:
    """Name every interpreter-host image the layout builds: the interpreter and each entrypoint."""
    return (
        "python",
        *(str(name) for name in layout["entrypoints"]),
        *(str(name) for name in layout.get("bundled_images", {})),
    )


def _package_relative(layout: Mapping[str, Any], key: str) -> str:
    if key == "executable":
        parent = Path(layout["paths"]["executable"]).parent.as_posix()
        return "." if parent in {"", "."} else parent
    if key not in layout["paths"]:
        raise _fail(f"names a layout path the package does not declare: {key!r}")
    return str(layout["paths"][key])


def compile_section(declaration: ApplicationEnvironment, layout: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the declaration for one build target into the contract's JSON section."""
    family = _platform_family(layout)
    built = images(layout)
    declared = {entry["image"] for entry in declaration.profiles.values()}
    if declared != set(built):
        raise _fail(f"profiles must cover exactly the built images {sorted(built)}; declared {sorted(declared)}")
    authority = _package_relative(layout, declaration.authority.value)

    def fixed(value: FixedValue) -> dict[str, str]:
        if value.source == "layout_path":
            return {"name": value.name, "source": "package", "value": _package_relative(layout, value.value)}
        if value.source == "image":
            if value.value not in built:
                raise _fail(f"fixed value {value.name} names an image the package does not build: {value.value}")
            return {"name": value.name, "source": "image", "value": value.value}
        return {"name": value.name, "source": "value", "value": value.value}

    profiles = []
    for name, entry in declaration.profiles.items():
        base = [item for group in entry["base_groups"] for item in declaration.base[family][group]]
        profiles.append(
            {
                "name": name,
                "image": entry["image"],
                "inherit": entry["inherit"],
                "invoked": entry["invoked"],
                "base": base,
                "pins": entry["pins"],
                "operator": list(entry["operator"]),
                "pass": list(entry["pass"]),
                "fixed": [fixed(value) for value in entry["fixed"]],
                "slots": [{"name": slot.name, "kind": slot.kind, "required": slot.required} for slot in entry["slots"]],
                "package_path": entry["package_path"],
            }
        )
    invocations = [
        {
            "profile": invocation.profile,
            "image": declaration.profiles[invocation.profile]["image"],
            "arguments": [
                {"literal": argument.literal}
                if argument.literal is not None
                else {"slot": argument.slot, "kind": argument.kind, "minimum": argument.minimum}
                for argument in invocation.arguments
            ],
            "distinct": [list(pair) for pair in invocation.distinct],
            "greater": [list(pair) for pair in invocation.greater],
        }
        for invocation in declaration.invocations
        if invocation.platform in {family, "all"}
    ]
    path_entries = []
    for entry in declaration.path_entries:
        if entry in {"executable", "native"}:
            path_entries.append({"kind": "package", "value": _package_relative(layout, entry)})
        else:
            path_entries.append({"kind": entry, "value": declaration.path_external if entry == "external" else ""})
    return {
        "schema": SCHEMA,
        "platform_family": family,
        "names": {name: dict(entry) for name, entry in sorted(declaration.names.items())},
        "location_names": sorted(name for name, entry in declaration.names.items() if entry["role"] == "location"),
        "images": list(built),
        "pins": {
            "temporary": list(declaration.temporary),
            "authority": {"name": declaration.authority.name, "value": authority},
        },
        "path": {
            "entries": path_entries,
            "windows_system": {
                "variable": declaration.windows_system[0],
                "subpaths": list(declaration.windows_system[1]),
            },
            "posix_system": list(declaration.posix_system),
        },
        "profiles": profiles,
        "invocations": invocations,
        "native_host": {
            "launch_profile_refused": declaration.native_host["launch_profile_refused"],
            "refusals": list(declaration.native_host["refusals"]),
        },
        "vectors": [dict(vector) for vector in declaration.launch_vectors if vector["platform"] == family],
    }


def _rust_string(value: str) -> str:
    if not value.isascii() or any(character in value for character in '"\\') or not value.isprintable():
        raise _fail(f"cannot spell {value!r} as a contract literal")
    return f'"{value}"'


def _rust_strings(values: Sequence[str]) -> str:
    return "&[" + ", ".join(_rust_string(value) for value in values) + "]"


def _rust_text(value: str) -> str:
    # Vector values may hold path separators; JSON's escapes are valid Rust for printable ASCII.
    if not value.isascii() or not value.isprintable():
        raise _fail(f"cannot spell {value!r} as a contract literal")
    return json.dumps(value)


def _rust_pairs(values: Sequence[Sequence[str]]) -> str:
    return "&[" + ", ".join(f"({_rust_string(a)}, {_rust_string(b)})" for a, b in values) + "]"


def rust_lines(section: Mapping[str, Any]) -> list[str]:
    """Emit the compiled launch profiles and invocation tables as Rust constants."""
    lines = [
        "pub struct LaunchFixed { pub name: &'static str, pub source: &'static str, pub value: &'static str }",
        "pub struct LaunchSlot { pub name: &'static str, pub kind: &'static str, pub required: bool }",
        "pub struct LaunchProfile {",
        "    pub name: &'static str,",
        "    pub image: &'static str,",
        "    pub inherit: bool,",
        "    pub invoked: bool,",
        "    pub base: &'static [&'static str],",
        "    pub pins: bool,",
        "    pub operator: &'static [&'static str],",
        "    pub pass: &'static [&'static str],",
        "    pub fixed: &'static [LaunchFixed],",
        "    pub slots: &'static [LaunchSlot],",
        "    pub package_path: bool,",
        "}",
        "pub struct LaunchArgument { pub literal: Option<&'static str>, pub slot: Option<&'static str>, "
        "pub kind: Option<&'static str>, pub minimum: u64 }",
        "pub struct LaunchInvocation {",
        "    pub profile: &'static str,",
        "    pub image: &'static str,",
        "    pub arguments: &'static [LaunchArgument],",
        "    pub distinct: &'static [(&'static str, &'static str)],",
        "    pub greater: &'static [(&'static str, &'static str)],",
        "}",
        "pub struct LaunchPathEntry { pub kind: &'static str, pub value: &'static str }",
        "pub struct LaunchName { pub name: &'static str, pub kind: &'static str, pub role: &'static str }",
        f"pub const LAUNCH_SCHEMA: u32 = {section['schema']};",
        f"pub const LAUNCH_PROFILE_REFUSED_EXIT: u32 = {section['native_host']['launch_profile_refused']};",
        f"pub const LAUNCH_REFUSALS: &[&str] = {_rust_strings(section['native_host']['refusals'])};",
        f"pub const LAUNCH_IMAGES: &[&str] = {_rust_strings(section['images'])};",
        f"pub const LAUNCH_TEMPORARY_PINS: &[&str] = {_rust_strings(section['pins']['temporary'])};",
        f"pub const LAUNCH_AUTHORITY_PIN: &str = {_rust_string(section['pins']['authority']['name'])};",
        f"pub const LAUNCH_AUTHORITY_PATH: &str = {_rust_string(section['pins']['authority']['value'])};",
        "pub const LAUNCH_PATH_ENTRIES: &[LaunchPathEntry] = &["
        + ", ".join(
            f"LaunchPathEntry {{ kind: {_rust_string(entry['kind'])}, value: {_rust_string(entry['value'])} }}"
            for entry in section["path"]["entries"]
        )
        + "];",
        "pub const LAUNCH_WINDOWS_SYSTEM_VARIABLE: &str = "
        f"{_rust_string(section['path']['windows_system']['variable'])};",
        "pub const LAUNCH_WINDOWS_SYSTEM_SUBPATHS: &[&str] = "
        f"{_rust_strings(section['path']['windows_system']['subpaths'])};",
        f"pub const LAUNCH_POSIX_SYSTEM_PATH: &[&str] = {_rust_strings(section['path']['posix_system'])};",
        "pub const LAUNCH_NAMES: &[LaunchName] = &["
        + ", ".join(
            f"LaunchName {{ name: {_rust_string(name)}, kind: {_rust_string(entry['kind'])}, "
            f"role: {_rust_string(entry['role'])} }}"
            for name, entry in section["names"].items()
        )
        + "];",
        "pub const LAUNCH_PROFILES: &[LaunchProfile] = &[",
    ]
    for profile in section["profiles"]:
        fixed = ", ".join(
            f"LaunchFixed {{ name: {_rust_string(value['name'])}, source: {_rust_string(value['source'])}, "
            f"value: {_rust_string(value['value'])} }}"
            for value in profile["fixed"]
        )
        slots = ", ".join(
            f"LaunchSlot {{ name: {_rust_string(slot['name'])}, kind: {_rust_string(slot['kind'])}, "
            f"required: {str(slot['required']).lower()} }}"
            for slot in profile["slots"]
        )
        lines.append(
            f"    LaunchProfile {{ name: {_rust_string(profile['name'])}, image: {_rust_string(profile['image'])}, "
            f"inherit: {str(profile['inherit']).lower()}, invoked: {str(profile['invoked']).lower()}, "
            f"base: {_rust_strings(profile['base'])}, pins: {str(profile['pins']).lower()}, "
            f"operator: {_rust_strings(profile['operator'])}, pass: {_rust_strings(profile['pass'])}, "
            f"fixed: &[{fixed}], slots: &[{slots}], package_path: {str(profile['package_path']).lower()} }},"
        )
    lines.append("];")
    lines.append("pub const LAUNCH_INVOCATIONS: &[LaunchInvocation] = &[")
    for invocation in section["invocations"]:
        arguments = ", ".join(
            f"LaunchArgument {{ literal: Some({_rust_string(argument['literal'])}), "
            "slot: None, kind: None, minimum: 0 }"
            if "literal" in argument
            else f"LaunchArgument {{ literal: None, slot: Some({_rust_string(argument['slot'])}), "
            f"kind: Some({_rust_string(argument['kind'])}), minimum: {argument['minimum']} }}"
            for argument in invocation["arguments"]
        )
        lines.append(
            f"    LaunchInvocation {{ profile: {_rust_string(invocation['profile'])}, "
            f"image: {_rust_string(invocation['image'])}, arguments: &[{arguments}], "
            f"distinct: {_rust_pairs(invocation['distinct'])}, greater: {_rust_pairs(invocation['greater'])} }},"
        )
    lines.append("];")
    lines.append(
        "pub struct LaunchVector { pub name: &'static str, pub image: &'static str, "
        "pub arguments: &'static [&'static str], pub ambient: &'static [(&'static str, &'static str)], "
        "pub profile: Option<&'static str>, pub environment: &'static [(&'static str, &'static str)], "
        "pub path: Option<&'static [&'static str]>, pub refusal: Option<(&'static str, &'static str)> }"
    )
    lines.append("pub const LAUNCH_VECTORS: &[LaunchVector] = &[")
    for vector in section["vectors"]:

        def pairs(table: Mapping[str, str]) -> str:
            return "&[" + ", ".join(f"({_rust_text(k)}, {_rust_text(v)})" for k, v in table.items()) + "]"

        profile = "None" if vector["profile"] is None else f"Some({_rust_text(vector['profile'])})"
        path = "None" if vector["path"] is None else "Some(&[" + ", ".join(map(_rust_text, vector["path"])) + "])"
        refusal = (
            "None"
            if vector["refusal"] is None
            else f"Some(({_rust_text(vector['refusal']['code'])}, {_rust_text(vector['refusal']['subject'])}))"
        )
        lines.append(
            f"    LaunchVector {{ name: {_rust_text(vector['name'])}, image: {_rust_text(vector['image'])}, "
            f"arguments: &[{', '.join(map(_rust_text, vector['arguments']))}], ambient: {pairs(vector['ambient'])}, "
            f"profile: {profile}, environment: {pairs(vector['environment'])}, path: {path}, refusal: {refusal} }},"
        )
    lines.append("];")
    return lines


def c_lines(section: Mapping[str, Any]) -> list[str]:
    """Emit the launch refusal status and the image identities a C host passes to the platform library."""
    return [
        f"#define CADRUMO_LAUNCH_PROFILE_REFUSED_EXIT {section['native_host']['launch_profile_refused']}",
        *(f'#define CADRUMO_LAUNCH_IMAGE_{image.upper().replace("-", "_")} "{image}"' for image in section["images"]),
    ]


class LaunchRefusedError(Exception):
    """A reference launch the profile refuses; carries the closed code and subject."""

    def __init__(self, code: str, subject: str) -> None:
        """Keep the refusal's code and subject."""
        super().__init__(code, subject)
        self.code = code
        self.subject = subject


def _argument_value(kind: str, minimum: int, text: str, family: str) -> int | None:
    if not text.isascii() or not text.isdigit() or (text.startswith("0") and len(text) > 1):
        return None
    value = int(text)
    maximum = (1 << 64) - 2 if kind == "handle" else (1 << 31) - 1
    if kind not in ARGUMENT_KINDS or (kind == "handle") != (family == "windows"):
        return None
    return value if max(minimum, 1) <= value <= maximum else None


def _invocation_matches(invocation: Invocation, arguments: Sequence[str], family: str) -> bool:
    if len(invocation.arguments) != len(arguments):
        return False
    values: dict[str, int] = {}
    for declared, actual in zip(invocation.arguments, arguments, strict=True):
        if declared.literal is not None:
            if declared.literal != actual:
                return False
            continue
        value = _argument_value(str(declared.kind), declared.minimum, actual, family)
        if value is None or declared.slot is None:
            return False
        values[declared.slot] = value
    return all(values[a] != values[b] for a, b in invocation.distinct) and all(
        values[a] > values[b] for a, b in invocation.greater
    )


def reference_select(declaration: ApplicationEnvironment, family: str, image: str, arguments: Sequence[str]) -> str:
    """Select a profile name as the host must, independently of the native implementation."""
    for invocation in declaration.invocations:
        if invocation.platform not in {family, "all"}:
            continue
        if declaration.profiles[invocation.profile]["image"] == image and _invocation_matches(
            invocation, arguments, family
        ):
            return invocation.profile
    for name, profile in declaration.profiles.items():
        if profile["image"] == image and not profile["invoked"]:
            return name
    raise LaunchRefusedError("invocation_undeclared", image)


def reference_define(
    declaration: ApplicationEnvironment,
    family: str,
    profile_name: str,
    ambient: Mapping[str, str],
    *,
    package: str,
    root: str,
    layout_paths: Mapping[str, str],
    suffix: str,
) -> dict[str, str]:
    """Define a profile's environment as the host must, for vectors whose root is already resolved.

    Directory and executable launch parameters are not checked against a filesystem here.
    """
    path_type: type[PurePath] = PureWindowsPath if family == "windows" else PurePosixPath
    folded = family == "windows"

    def get(name: str) -> str | None:
        found = None
        for key, value in ambient.items():
            if (key.upper() == name.upper()) if folded else (key == name):
                found = value
        return found

    profile = declaration.profiles[profile_name]
    if profile["inherit"]:
        return dict(ambient)
    defined: dict[str, str] = {}

    def put(name: str, value: str) -> None:
        for key in [key for key in defined if (key.upper() == name.upper() if folded else key == name)]:
            del defined[key]
        defined[name] = value

    parameters: list[tuple[str, str]] = []
    for slot in profile["slots"]:
        value = get(slot.name)
        if value is None:
            if slot.required:
                raise LaunchRefusedError("launch_value_missing", slot.name)
            continue
        if slot.kind == "port" and not (value.isdigit() and value.isascii() and int(value) <= 0xFFFF):
            raise LaunchRefusedError("launch_value_malformed", slot.name)
        parameters.append((slot.name, value))
    base = [name for group in profile["base_groups"] for name in declaration.base[family][group]]
    for name in (*base, *profile["operator"], *profile["pass"]):
        value = get(name)
        if value is not None:
            put(name, value)
    package_path = path_type(package)
    if profile["pins"]:
        member = declaration.temporary_member["name"]
        admitted = member in profile["operator"] or member in profile["pass"]
        override = get(member) if admitted else None
        temporary = path_type(root) / (override or declaration.temporary_member["default"])
        put(declaration.root["variable"], str(path_type(root)))
        for name in declaration.temporary:
            put(name, str(temporary))
        put(declaration.authority.name, str(package_path / layout_paths[declaration.authority.value]))
    for fixed in profile["fixed"]:
        if fixed.source == "value":
            put(fixed.name, fixed.value)
        elif fixed.source == "image":
            image = package_path / (layout_paths["executable"] if fixed.value == "python" else layout_paths["native"])
            put(fixed.name, str(image if fixed.value == "python" else image / f"{fixed.value}{suffix}"))
        else:
            put(fixed.name, str(package_path / layout_paths[fixed.value]))
    for name, value in parameters:
        put(name, value)
    if profile["package_path"]:
        entries: list[str] = []
        for entry in declaration.path_entries:
            if entry == "executable":
                entries.append(str(package_path))
            elif entry == "native":
                entries.append(str(package_path / layout_paths["native"]))
            elif entry == "system":
                if family == "windows":
                    system = get(declaration.windows_system[0])
                    if system is None:
                        raise ValueError("The Windows system directory variable is missing")
                    entries.append(str(path_type(system, *declaration.windows_system[1])))
                else:
                    entries.extend(declaration.posix_system)
        put("PATH", (";" if family == "windows" else ":").join(entries))
    return defined
