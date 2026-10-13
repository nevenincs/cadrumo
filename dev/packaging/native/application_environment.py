"""Validate the package's application environment declaration and compile its launch profiles."""

from __future__ import annotations

import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
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
NAME_ROLES = frozenset({"location", "operator", "package", "pin", "fixed", "slot"})
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


def parse(text: str) -> ApplicationEnvironment:
    """Validate the declaration's text against schema 1."""
    try:
        document = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise _fail(f"is not valid TOML: {error}") from error
    _keys(
        document, "the declaration", {"schema", "names", "groups", "base", "pins", "path", "profiles"}, {"invocations"}
    )
    if document["schema"] != SCHEMA or isinstance(document["schema"], bool):
        raise _fail(f"schema must be {SCHEMA}")
    names = _names(document["names"])
    groups = _groups(document["groups"], names)
    base = _base(document["base"])
    pins = _table(document["pins"], "pins")
    _keys(pins, "pins", {"temporary", "authority"})
    temporary = _strings(pins["temporary"], "pins.temporary", _NAME)
    if any(names.get(name, {}).get("role") != "pin" for name in temporary):
        raise _fail("pins.temporary must list declared pin names")
    authority = _fixed(pins["authority"], "pins.authority", names, role="fixed")
    if authority.source != "layout_path":
        raise _fail("pins.authority must name a layout path")
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
    profiles = _profiles(document["profiles"], names, groups)
    invocations = _invocations(document.get("invocations", []))
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
    )


def load(root: Path) -> ApplicationEnvironment:
    """Read and validate the declaration from a source tree."""
    return parse((root / DECLARATION).read_text(encoding="utf-8"))


def _platform_family(layout: Mapping[str, Any]) -> str:
    return "windows" if layout["backend"] == "windows" else "posix"


def images(layout: Mapping[str, Any]) -> tuple[str, ...]:
    """Name every interpreter-host image the layout builds: the interpreter and each entrypoint."""
    return ("python", *(str(name) for name in layout["entrypoints"]))


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
    }


def _rust_string(value: str) -> str:
    if not value.isascii() or any(character in value for character in '"\\') or not value.isprintable():
        raise _fail(f"cannot spell {value!r} as a contract literal")
    return f'"{value}"'


def _rust_strings(values: Sequence[str]) -> str:
    return "&[" + ", ".join(_rust_string(value) for value in values) + "]"


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
    return lines


def c_lines(section: Mapping[str, Any]) -> list[str]:
    """Emit the image identities a C host passes to the platform library."""
    return [f'#define CADRUMO_LAUNCH_IMAGE_{image.upper().replace("-", "_")} "{image}"' for image in section["images"]]
