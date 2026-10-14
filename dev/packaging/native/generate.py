"""Project the package declarations into native build inputs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev.locales.manager_chrome import manager_chrome_strings

from . import application_environment
from .application_environment import ApplicationEnvironment, channel_directory
from .identity import identity
from .layout import bundled_image_files, distribution_target, entrypoint_files, load_layout
from .linux_desktop_runtime import declaration as desktop_runtime_declaration
from .linux_desktop_runtime import desktop_path
from .runtime_exit_reasons import runtime_exit_section, rust_runtime_exit_reasons
from .stable_output import write_text
from .storage_vectors import (
    INVALID_NATIVE_PATH_BYTES,
    INVALID_NATIVE_PATH_UTF16,
    storage_path_vectors,
    storage_root_vectors,
)
from .transport_contract import rust_transport, transport_section

CONTRACT_SCHEMA = 1


def _rust_string(value: str) -> str:
    value.encode("utf-8")  # Native OS strings have explicit fixture encodings.
    escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
    return (
        '"'
        + "".join(
            escapes.get(character, f"\\u{{{ord(character):x}}}" if ord(character) < 32 else character)
            for character in value
        )
        + '"'
    )


def _rust_strings(values: Iterable[str]) -> str:
    return "&[" + ",".join(map(_rust_string, values)) + "]"


def _rust_option(value: str | None) -> str:
    return "None" if value is None else f"Some({_rust_string(value)})"


# The kinds the filtering hosts validate for a received host pin.
_INHERITED_KINDS = {"DIRECTORY_PATH": "directory_path", "OPAQUE": "opaque"}


def _environment_section(declaration: ApplicationEnvironment) -> dict[str, Any]:
    """Project the declaration onto the classes a strict child filter clears and the pins it sets."""
    root = declaration.root["variable"]
    authority = declaration.authority.name
    return {
        "cleared": {
            "prefixes": list(declaration.host_classes["cleared_prefixes"]),
            "names": list(declaration.host_classes["cleared_names"]),
            "namespace_prefix": declaration.host_classes["namespace_prefix"],
        },
        "pinned": [root, *declaration.temporary],
        "host_inherited": {
            "all": [authority],
            "windows": [],
            "fields": [{"name": authority, "kind": _INHERITED_KINDS["DIRECTORY_PATH"]}],
        },
    }


def _mode_section(layout: dict[str, Any], declaration: ApplicationEnvironment) -> dict[str, Any]:
    return {
        "package_manifest": layout["files"]["package_manifest"],
        "package_root_from_executable": layout["package_root_from_executable"],
        "checkout_marker": declaration.root["checkout_marker"],
    }


def _rust_root_and_environment(contract: dict[str, Any]) -> list[str]:
    root, environment, mode = contract["root"], contract["environment"], contract["mode"]
    lines = [
        "pub struct InstalledBaseCandidate { pub variable: &'static str, pub subpath: &'static [&'static str] }",
        "pub struct InstalledDefault {",
        "    pub platform: &'static str,",
        "    pub candidates: &'static [InstalledBaseCandidate],",
        "    pub home_variable: &'static str,",
        "}",
        "pub struct StorageRootVector {",
        "    pub name: &'static str,",
        "    pub platform: &'static str,",
        "    pub mode: &'static str,",
        "    pub environment: &'static [(&'static str, &'static str)],",
        "    pub checkout: Option<&'static str>,",
        "    pub known_folder: Option<&'static str>,",
        "    pub channel: &'static str,",
        "    pub expected_root: Option<&'static str>,",
        "    pub refusal: Option<&'static str>,",
        "    pub invalid_environment: &'static [&'static str],",
        "    pub invalid_checkout: bool,",
        "    pub invalid_known_folder: bool,",
        "}",
        f"pub const CONTRACT_SCHEMA: u32 = {contract['schema']};",
        f"pub const BUILD_CHANNEL: &str = {_rust_string(contract['channel']['build'])};",
        f"pub const ROOT_VARIABLE: &str = {_rust_string(root['variable'])};",
        f"pub const DEVELOPMENT_ROOT_VARIABLE: &str = {_rust_string(root['development_variable'])};",
        f"pub const DEVELOPMENT_ROOT_PRECEDENCE: &[&str] = {_rust_strings(root['precedence']['development'])};",
        f"pub const INSTALLED_ROOT_PRECEDENCE: &[&str] = {_rust_strings(root['precedence']['installed'])};",
        f"pub const DEVELOPMENT_DEFAULT: &str = {_rust_string(root['development_default'])};",
        f"pub const PRODUCT_DIRECTORY: &str = {_rust_string(root['channel']['product_directory'])};",
        f"pub const STABLE_CHANNEL: &str = {_rust_string(root['channel']['stable'])};",
        f"pub const CHANNEL_SEPARATOR: &str = {_rust_string(root['channel']['separator'])};",
        f"pub const DEVELOPMENT_RELATIVE_OVERRIDE: &str = {_rust_string(root['relative_override']['development'])};",
        f"pub const INSTALLED_RELATIVE_OVERRIDE: &str = {_rust_string(root['relative_override']['installed'])};",
        f"pub const POSIX_DIRECTORY_MODE: u32 = {root['posix_directory_mode']:#o};",
        f"pub const ROOT_REFUSALS: &[&str] = {_rust_strings(root['refusals'])};",
        "pub const INSTALLED_DEFAULTS: &[InstalledDefault] = &[",
    ]
    lines.pop()  # The installed-default array follows scalar declarations.
    lines.extend(
        f"pub const ROOT_REFUSAL_{refusal.upper()}: &str = {_rust_string(refusal)};" for refusal in root["refusals"]
    )
    lines.extend(
        f"pub const STORAGE_{name.upper()}: bool = {str(value).lower()};" for name, value in root["path_rules"].items()
    )
    lines.extend(
        f"pub const INHERITED_KIND_{name}: &str = {_rust_string(kind)};" for name, kind in _INHERITED_KINDS.items()
    )
    lines.append("pub const INSTALLED_DEFAULTS: &[InstalledDefault] = &[")
    for rule in root["installed_defaults"]:
        candidates = ", ".join(
            f"InstalledBaseCandidate {{ variable: {_rust_string(candidate['variable'])}, "
            f"subpath: {_rust_strings(candidate['subpath'])} }}"
            for candidate in rule["candidates"]
        )
        lines.append(
            f"    InstalledDefault {{ platform: {_rust_string(rule['platform'])}, candidates: &[{candidates}], "
            f"home_variable: {_rust_string(rule['home_variable'])} }},"
        )
    lines.append("];")
    lines += [
        f"pub const CLEARED_PREFIXES: &[&str] = {_rust_strings(environment['cleared']['prefixes'])};",
        f"pub const CLEARED_NAMES: &[&str] = {_rust_strings(environment['cleared']['names'])};",
        f"pub const NAMESPACE_PREFIX: &str = {_rust_string(environment['cleared']['namespace_prefix'])};",
        f"pub const PINNED_ENV: &[&str] = {_rust_strings(environment['pinned'])};",
        f"pub const HOST_INHERITED_ENV: &[&str] = {_rust_strings(environment['host_inherited']['all'])};",
        f"pub const WINDOWS_HOST_INHERITED_ENV: &[&str] = {_rust_strings(environment['host_inherited']['windows'])};",
        "pub struct InheritedEnvironmentField { pub name: &'static str, pub kind: &'static str }",
        "pub const HOST_INHERITED_FIELDS: &[InheritedEnvironmentField] = &["
        + ",".join(
            f"InheritedEnvironmentField {{ name: {_rust_string(field['name'])}, kind: {_rust_string(field['kind'])} }}"
            for field in environment["host_inherited"]["fields"]
        )
        + "];",
        f"pub const MODE_PACKAGE_MANIFEST: &str = {_rust_string(mode['package_manifest'])};",
        f"pub const MODE_PACKAGE_ROOT_FROM_EXECUTABLE: &str = {_rust_string(mode['package_root_from_executable'])};",
        f"pub const MODE_CHECKOUT_MARKER: &str = {_rust_string(mode['checkout_marker'])};",
        "pub const STORAGE_ROOT_VECTORS: &[StorageRootVector] = &[",
    ]
    for vector in contract["vectors"]:
        pairs = ", ".join(
            f"({_rust_string(name)}, {_rust_string(value)})" for name, value in sorted(vector["environment"].items())
        )
        lines.append(
            "    StorageRootVector { "
            f"name: {_rust_string(vector['name'])}, platform: {_rust_string(vector['platform'])}, "
            f"mode: {_rust_string(vector['mode'])}, environment: &[{pairs}], "
            f"checkout: {_rust_option(vector['checkout'])}, known_folder: {_rust_option(vector['known_folder'])}, "
            f"channel: {_rust_string(vector['channel'])}, expected_root: {_rust_option(vector['expected_root'])}, "
            f"refusal: {_rust_option(vector['refusal'])}, "
            f"invalid_environment: {_rust_strings(vector['invalid_environment'])}, "
            f"invalid_checkout: {str(vector['invalid_checkout']).lower()}, "
            f"invalid_known_folder: {str(vector['invalid_known_folder']).lower()} }},"
        )
    lines.append("];")
    lines += [
        f"pub const INVALID_NATIVE_PATH_BYTES: &[u8] = &{list(INVALID_NATIVE_PATH_BYTES)};",
        f"pub const INVALID_NATIVE_PATH_UTF16: &[u16] = &{list(INVALID_NATIVE_PATH_UTF16)};",
        "pub struct StoragePathVector { pub name: &'static str, pub components: &'static [&'static str], "
        "pub directories: &'static [&'static str], pub files: &'static [&'static str], "
        "pub links: &'static [(&'static str, &'static str)], "
        "pub expected_components: Option<&'static [&'static str]>, pub refusal: Option<&'static str> }",
        "pub const STORAGE_PATH_VECTORS: &[StoragePathVector] = &[",
    ]
    for vector in contract["path_vectors"]:
        links = ",".join(f"({_rust_string(name)},{_rust_string(target)})" for name, target in vector["links"])
        expected = (
            "None" if vector["expected_components"] is None else f"Some({_rust_strings(vector['expected_components'])})"
        )
        lines.append(
            f"StoragePathVector {{ name: {_rust_string(vector['name'])}, "
            f"components: {_rust_strings(vector['components'])}, directories: {_rust_strings(vector['directories'])}, "
            f"files: {_rust_strings(vector['files'])}, links: &[{links}], "
            f"expected_components: {expected}, refusal: {_rust_option(vector['refusal'])} }},"
        )
    lines.append("];")
    return lines


def generate(root: Path, destination: Path, channel: str = "stable", *, target: str | None = None) -> None:
    """Write C, Rust and inspection projections from their authored owners in one run.

    ``channel`` is the release channel the identity projection validated for this build.
    """
    layout = load_layout(target, root=root)
    declaration = application_environment.load(root)
    launch = application_environment.compile_section(declaration, layout)
    release = identity(distribution_target(layout), channel, project_file=root / "pyproject.toml")
    build_channel = release.channel
    version = (root / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    if not version.startswith((root / ".python-version").read_text(encoding="utf-8").strip() + "."):
        raise ValueError("Exact CPython build must belong to the development minor")
    components, temporary = declaration.components, declaration.temporary_member
    environment = _environment_section(declaration)
    invalid_path_refusal = "invalid_path_input"
    if invalid_path_refusal not in declaration.root["refusals"]:
        raise ValueError("The invalid native path refusal must be a declared root refusal")
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "channel": {"build": build_channel, "installed_directory": channel_directory(declaration.root, build_channel)},
        "layout": layout,
        "linux_desktop_runtime": desktop_runtime_declaration(layout) if bool(desktop_path(layout)) else None,
        "installation_identity": {"application_id": release.application_id, "channel": release.channel},
        "python": version,
        "release": {
            "platform": layout["platform"],
            "abi": layout["abi"],
            "target": release.target,
            "python": version,
            "version": release.version,
            "channel": release.channel,
            "cohort": list(PRODUCT_IDENTITY.cohort_distributions),
        },
        "root": dict(declaration.root),
        "runtime_transport": transport_section(),
        "environment": environment,
        "mode": _mode_section(layout, declaration),
        "vectors": [vector.as_contract() for vector in storage_root_vectors(root)],
        "path_vectors": [vector.as_contract() for vector in storage_path_vectors()],
        "invalid_native_path": {
            "posix_bytes": list(INVALID_NATIVE_PATH_BYTES),
            "windows_utf16": list(INVALID_NATIVE_PATH_UTF16),
            "refusal": invalid_path_refusal,
        },
        "runtime_exit": runtime_exit_section(declaration.native_host),
        "native_host": dict(declaration.native_host),
        "application_environment": launch,
        "desktop_defaults": {
            "console_workspace": components["console_workspace"],
            "webview": components["webview"],
            "logs": components["logs"],
            "log_variable": components["log_variable"],
            "log_file": components["log_file"],
            "manager_log_file": components["manager_log_file"],
            "log_format": components["log_format"],
            "log_max_bytes": components["log_max_bytes"],
            "log_backups": components["log_backups"],
            "output_language": components["language_default"],
            "output_language_variable": components["language_variable"],
        },
    }
    package_strings = {
        **{key.upper(): value for key, value in layout["paths"].items()},
        "TEMPORARY_ENV": temporary["name"],
        "TEMPORARY_DEFAULT": temporary["default"],
    }
    rust = [f"pub const ABI: u32 = {layout['abi']};"]
    discovery = {"layout": layout, "installation_identity": contract["installation_identity"]}
    rust.append(f"pub const INSTALLATION_CONTRACT: &str = {_rust_string(json.dumps(discovery))};")
    rust.extend(
        [
            f"pub const MANAGER_LOG: &str = {_rust_string(components['manager_log_file'])};",
            f"pub const MANAGER_PREFERENCES: &str = {_rust_string(components['manager_preferences'])};",
            f"pub const MANAGER_FAILED_VERSIONS: &str = {_rust_string(components['manager_failed_versions'])};",
            f"pub const MANAGER_LANGUAGE_ENV: &str = {_rust_string(components['language_variable'])};",
            f"pub const MANAGER_LANGUAGE_DEFAULT: &str = {_rust_string(components['language_default'])};",
            "pub const MANAGER_STRINGS_JSON: &str = "
            f"{_rust_string(json.dumps(manager_chrome_strings(), ensure_ascii=False, sort_keys=True))};",
            f"pub const LOG_MAX_BYTES: u64 = {contract['desktop_defaults']['log_max_bytes']};",
            f"pub const LOG_BACKUPS: u32 = {contract['desktop_defaults']['log_backups']};",
        ]
    )
    rust.extend(f"pub const {key}: &str = {_rust_string(value)};" for key, value in package_strings.items())
    rust.append(f"pub const TEMPORARY_CREATE_EXPLICIT: bool = {str(temporary['create_explicit']).lower()};")
    # Declared entrypoint images live in NATIVE; the platform context maps them back to the package root.
    entrypoints = [
        Path(relative).name for relative in (*entrypoint_files(layout).values(), *bundled_image_files(layout).values())
    ]
    rust.append(f"pub const ENTRYPOINT_FILES: &[&str] = {_rust_strings(entrypoints)};")
    rust.extend(_rust_root_and_environment(contract))
    rust.extend(rust_transport(contract["runtime_transport"]))
    rust.extend(rust_runtime_exit_reasons(contract["runtime_exit"]))
    rust.extend(application_environment.rust_lines(launch))
    destination.mkdir(parents=True, exist_ok=True)
    write_text(destination / "contract.rs", "\n".join(rust) + "\n")
    write_text(
        destination / "contract.h",
        f'#define CADRUMO_PYTHON_VERSION "{version}"\n#define CADRUMO_PLATFORM_ABI {layout["abi"]}\n'
        f"#define CADRUMO_CONTRACT_SCHEMA {CONTRACT_SCHEMA}\n"
        + "".join(f"{line}\n" for line in application_environment.c_lines(launch)),
    )
    write_text(destination / "contract.json", json.dumps(contract, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--target")
    args = parser.parse_args()
    generate(Path(__file__).resolve().parents[3], args.destination, args.channel, target=args.target)
