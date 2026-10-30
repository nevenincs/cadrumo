"""Compile the application environment declaration into native contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .environment_declaration_constants import SCHEMA
from .environment_declaration_primitives import _fail
from .environment_models import ApplicationEnvironment, FixedValue, InvocationArgument


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


def _compiled_argument(argument: InvocationArgument) -> dict[str, Any]:
    if argument.literal is not None:
        return {"literal": argument.literal}
    typed = {"slot": argument.slot, "kind": argument.kind, "minimum": argument.minimum}
    return typed if argument.option is None else {"option": argument.option, **typed}


def compile_section(declaration: ApplicationEnvironment, layout: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the declaration for one build target into the contract's JSON section."""
    family = _platform_family(layout)
    built = images(layout)
    declared = {entry["image"] for entry in declaration.profiles.values()}
    if declared != set(built):
        raise _fail(f"profiles must cover exactly the built images {sorted(built)}; declared {sorted(declared)}")
    if set(declaration.package_values) != {fixed.name for fixed in declaration.package_fixed}:
        raise _fail("package-fixed values must be resolved before contract generation")
    authority = _package_relative(layout, declaration.authority.value)

    profiles = _compiled_profiles(declaration, layout, built, family)
    invocations = _compiled_invocations(declaration, family)
    path_entries = _compiled_path_entries(declaration, layout)
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
            "external_defaults": [
                {
                    "platform": default.platform,
                    "variable": default.variable,
                    "path": default.path,
                    "subpaths": list(default.subpaths),
                }
                for default in declaration.external_path_defaults
            ],
            "windows_system": {
                "variable": declaration.windows_system[0],
                "subpaths": list(declaration.windows_system[1]),
            },
            "posix_system": list(declaration.posix_system),
        },
        "profiles": profiles,
        "package_fixed": dict(declaration.package_values),
        "invocations": invocations,
        "native_host": {
            "launch_profile_refused": declaration.native_host["launch_profile_refused"],
            "refusals": list(declaration.native_host["refusals"]),
        },
    }


def vectors_for(declaration: ApplicationEnvironment, layout: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Select the launch conformance vectors of the layout's platform family.

    They are test inputs: the native resolver replays them in its tests, and no packaged
    contract carries them.
    """
    family = _platform_family(layout)
    return [dict(vector) for vector in declaration.launch_vectors if vector["platform"] == family]


def _compiled_invocations(declaration: ApplicationEnvironment, family: str) -> list[dict[str, Any]]:
    invocations = [
        {
            "profile": invocation.profile,
            "image": declaration.profiles[invocation.profile]["image"],
            "arguments": [_compiled_argument(argument) for argument in invocation.arguments],
            "distinct": [list(pair) for pair in invocation.distinct],
            "greater": [list(pair) for pair in invocation.greater],
        }
        for invocation in declaration.invocations
        if invocation.platform in {family, "all"}
    ]
    return invocations


def _compiled_path_entries(declaration: ApplicationEnvironment, layout: Mapping[str, Any]) -> list[dict[str, str]]:
    path_entries = []
    for entry in declaration.path_entries:
        if entry in {"executable", "native"}:
            path_entries.append({"kind": "package", "value": _package_relative(layout, entry)})
        elif entry == "external_defaults":
            path_entries.append({"kind": entry, "value": declaration.path_external})
        else:
            path_entries.append({"kind": entry, "value": declaration.path_external if entry == "external" else ""})
    return path_entries


def _compiled_fixed(value: FixedValue, layout: Mapping[str, Any], built: tuple[str, ...]) -> dict[str, str]:
    if value.source == "layout_path":
        return {"name": value.name, "source": "package", "value": _package_relative(layout, value.value)}
    if value.source == "image":
        if value.value not in built:
            raise _fail(f"fixed value {value.name} names an image the package does not build: {value.value}")
        return {"name": value.name, "source": "image", "value": value.value}
    return {"name": value.name, "source": "value", "value": value.value}


def _compiled_profiles(
    declaration: ApplicationEnvironment,
    layout: Mapping[str, Any],
    built: tuple[str, ...],
    family: str,
) -> list[dict[str, Any]]:
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
                "pins": list(entry["pins"]),
                "operator": list(entry["operator"]),
                "pass": list(entry["pass"]),
                "prefix": entry["prefix"],
                "prefix_refused": list(entry["prefix_refused"]),
                "fixed": [_compiled_fixed(value, layout, built) for value in entry["fixed"]],
                "slots": [{"name": slot.name, "kind": slot.kind, "required": slot.required} for slot in entry["slots"]],
                "package_path": entry["package_path"],
            }
        )
    return profiles


def _rust_string(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise _fail("cannot spell a value as a contract literal") from None
    escaped = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return (
        '"'
        + "".join(
            escaped.get(character, f"\\u{{{ord(character):x}}}" if ord(character) < 32 else character)
            for character in value
        )
        + '"'
    )


def _rust_strings(values: Sequence[str]) -> str:
    return "&[" + ", ".join(_rust_string(value) for value in values) + "]"


def _rust_text(value: str) -> str:
    return _rust_string(value)


def _rust_pairs(values: Sequence[Sequence[str]]) -> str:
    return "&[" + ", ".join(f"({_rust_string(a)}, {_rust_string(b)})" for a, b in values) + "]"


def _rust_argument(argument: Mapping[str, Any]) -> str:
    if "literal" in argument:
        return (
            f"LaunchArgument {{ literal: Some({_rust_string(argument['literal'])}), option: None, "
            "slot: None, kind: None, minimum: 0 }"
        )
    option = f"Some({_rust_string(argument['option'])})" if "option" in argument else "None"
    return (
        f"LaunchArgument {{ literal: None, option: {option}, slot: Some({_rust_string(argument['slot'])}), "
        f"kind: Some({_rust_string(argument['kind'])}), minimum: {argument['minimum']} }}"
    )


def rust_lines(section: Mapping[str, Any]) -> list[str]:
    """Emit the compiled launch profiles and invocation tables as Rust constants."""

    def rust_option_string(value: str | None) -> str:
        return "None" if value is None else f"Some({_rust_string(value)})"

    lines = [
        "pub struct LaunchFixed { pub name: &'static str, pub source: &'static str, pub value: &'static str }",
        "pub struct LaunchSlot { pub name: &'static str, pub kind: &'static str, pub required: bool }",
        "pub struct LaunchProfile {",
        "    pub name: &'static str,",
        "    pub image: &'static str,",
        "    pub inherit: bool,",
        "    pub invoked: bool,",
        "    pub base: &'static [&'static str],",
        "    pub pins: &'static [&'static str],",
        "    pub operator: &'static [&'static str],",
        "    pub pass: &'static [&'static str],",
        "    pub prefix: &'static str,",
        "    pub prefix_refused: &'static [&'static str],",
        "    pub fixed: &'static [LaunchFixed],",
        "    pub slots: &'static [LaunchSlot],",
        "    pub package_path: bool,",
        "}",
        "pub struct LaunchArgument { pub literal: Option<&'static str>, pub option: Option<&'static str>, "
        "pub slot: Option<&'static str>, pub kind: Option<&'static str>, pub minimum: u64 }",
        "pub struct LaunchInvocation {",
        "    pub profile: &'static str,",
        "    pub image: &'static str,",
        "    pub arguments: &'static [LaunchArgument],",
        "    pub distinct: &'static [(&'static str, &'static str)],",
        "    pub greater: &'static [(&'static str, &'static str)],",
        "}",
        "pub struct LaunchPathEntry { pub kind: &'static str, pub value: &'static str }",
        "pub struct LaunchExternalPathDefault { pub platform: &'static str, pub variable: Option<&'static str>, "
        "pub path: &'static str, pub subpaths: &'static [&'static str] }",
        "pub struct LaunchName { pub name: &'static str, pub kind: &'static str, pub role: &'static str }",
        f"pub const LAUNCH_SCHEMA: u32 = {section['schema']};",
        f"pub const LAUNCH_PROFILE_REFUSED_EXIT: u32 = {section['native_host']['launch_profile_refused']};",
        f"pub const LAUNCH_REFUSALS: &[&str] = {_rust_strings(section['native_host']['refusals'])};",
        f"pub const LAUNCH_IMAGES: &[&str] = {_rust_strings(section['images'])};",
        f"pub const LAUNCH_PACKAGE_FIXED: &[(&str, &str)] = {_rust_pairs(tuple(section['package_fixed'].items()))};",
        f"pub const LAUNCH_TEMPORARY_PINS: &[&str] = {_rust_strings(section['pins']['temporary'])};",
        f"pub const LAUNCH_AUTHORITY_PIN: &str = {_rust_string(section['pins']['authority']['name'])};",
        f"pub const LAUNCH_AUTHORITY_PATH: &str = {_rust_string(section['pins']['authority']['value'])};",
        "pub const LAUNCH_PATH_ENTRIES: &[LaunchPathEntry] = &["
        + ", ".join(
            f"LaunchPathEntry {{ kind: {_rust_string(entry['kind'])}, value: {_rust_string(entry['value'])} }}"
            for entry in section["path"]["entries"]
        )
        + "];",
        "pub const LAUNCH_EXTERNAL_PATH_DEFAULTS: &[LaunchExternalPathDefault] = &["
        + ", ".join(
            "LaunchExternalPathDefault { "
            f"platform: {_rust_string(default['platform'])}, "
            f"variable: {rust_option_string(default['variable'])}, "
            f"path: {_rust_string(default['path'])}, "
            f"subpaths: {_rust_strings(default['subpaths'])} }}"
            for default in section["path"]["external_defaults"]
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
            f"base: {_rust_strings(profile['base'])}, pins: {_rust_strings(profile['pins'])}, "
            f"operator: {_rust_strings(profile['operator'])}, pass: {_rust_strings(profile['pass'])}, "
            f"prefix: {_rust_string(profile['prefix'])}, "
            f"prefix_refused: {_rust_strings(profile['prefix_refused'])}, "
            f"fixed: &[{fixed}], slots: &[{slots}], package_path: {str(profile['package_path']).lower()} }},"
        )
    lines.append("];")
    lines.append("pub const LAUNCH_INVOCATIONS: &[LaunchInvocation] = &[")
    for invocation in section["invocations"]:
        arguments = ", ".join(_rust_argument(argument) for argument in invocation["arguments"])
        lines.append(
            f"    LaunchInvocation {{ profile: {_rust_string(invocation['profile'])}, "
            f"image: {_rust_string(invocation['image'])}, arguments: &[{arguments}], "
            f"distinct: {_rust_pairs(invocation['distinct'])}, greater: {_rust_pairs(invocation['greater'])} }},"
        )
    lines.append("];")
    return lines


def rust_vector_lines(vectors: Sequence[Mapping[str, Any]]) -> list[str]:
    """Emit the launch conformance vectors for the native resolver's tests only."""
    lines = [
        "pub struct LaunchVector { pub name: &'static str, pub image: &'static str, "
        "pub arguments: &'static [&'static str], pub ambient: &'static [(&'static str, &'static str)], "
        "pub profile: Option<&'static str>, pub environment: &'static [(&'static str, &'static str)], "
        "pub path: Option<&'static [&'static str]>, pub refusal: Option<(&'static str, &'static str)> }",
        "pub const LAUNCH_VECTORS: &[LaunchVector] = &[",
    ]
    for vector in vectors:

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
