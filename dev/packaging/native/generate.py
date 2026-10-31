"""Project the package declarations into native build inputs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, TypedDict

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo_client.contracts.deadline_budget import DEFAULT_TIMEOUT_POLICY

from . import application_environment, environment_compile
from .build_directory import require_enrolled_output
from .discovered_inputs import record_discovered_inputs
from .environment_models import ApplicationEnvironment
from .environment_root import channel_directory
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


def _package_section(layout: dict[str, Any]) -> dict[str, Any]:
    """Project where an image finds its package root and the manifest that proves it is installed."""
    return {
        "package_manifest": layout["files"]["package_manifest"],
        "package_root_from_executable": layout["package_root_from_executable"],
    }


class _PathVector(TypedDict):
    name: str
    components: list[str]
    directories: list[str]
    files: list[str]
    links: list[list[str]]
    expected_components: list[str] | None
    refusal: str | None


def _rust_path_vectors(lines: list[str], vectors: list[_PathVector]) -> None:
    for vector in vectors:
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


def _rust_root_and_environment(contract: dict[str, Any]) -> list[str]:
    root, environment, package = contract["root"], contract["environment"], contract["package"]
    lines = [
        "pub struct InstalledBaseCandidate { pub variable: &'static str, pub subpath: &'static [&'static str] }",
        "pub struct InstalledDefault {",
        "    pub platform: &'static str,",
        "    pub candidates: &'static [InstalledBaseCandidate],",
        "    pub home_variable: &'static str,",
        "}",
        f"pub const CONTRACT_SCHEMA: u32 = {contract['schema']};",
        f"pub const BUILD_CHANNEL: &str = {_rust_string(contract['channel']['build'])};",
        f"pub const ROOT_VARIABLE: &str = {_rust_string(root['variable'])};",
        f"pub const PRODUCT_DIRECTORY: &str = {_rust_string(root['channel']['product_directory'])};",
        f"pub const STABLE_CHANNEL: &str = {_rust_string(root['channel']['stable'])};",
        f"pub const CHANNEL_SEPARATOR: &str = {_rust_string(root['channel']['separator'])};",
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
        f"pub const PACKAGE_MANIFEST: &str = {_rust_string(package['package_manifest'])};",
        f"pub const PACKAGE_ROOT_FROM_EXECUTABLE: &str = {_rust_string(package['package_root_from_executable'])};",
    ]
    lines += [
        f"pub const INVALID_NATIVE_PATH_BYTES: &[u8] = &{list(INVALID_NATIVE_PATH_BYTES)};",
        f"pub const INVALID_NATIVE_PATH_UTF16: &[u16] = &{list(INVALID_NATIVE_PATH_UTF16)};",
        "pub struct StoragePathVector { pub name: &'static str, pub components: &'static [&'static str], "
        "pub directories: &'static [&'static str], pub files: &'static [&'static str], "
        "pub links: &'static [(&'static str, &'static str)], "
        "pub expected_components: Option<&'static [&'static str]>, pub refusal: Option<&'static str> }",
        "pub const STORAGE_PATH_VECTORS: &[StoragePathVector] = &[",
    ]
    _rust_path_vectors(lines, contract["path_vectors"])
    lines.append("];")
    return lines


def _rust_root_vectors(vectors: list[dict[str, Any]]) -> list[str]:
    """Project the root vectors the native resolver replays in its tests only."""
    lines = [
        "pub struct StorageRootVector {",
        "    pub name: &'static str,",
        "    pub platform: &'static str,",
        "    pub environment: &'static [(&'static str, &'static str)],",
        "    pub known_folder: Option<&'static str>,",
        "    pub channel: &'static str,",
        "    pub expected_root: Option<&'static str>,",
        "    pub refusal: Option<&'static str>,",
        "    pub invalid_environment: &'static [&'static str],",
        "    pub invalid_known_folder: bool,",
        "}",
        "pub const STORAGE_ROOT_VECTORS: &[StorageRootVector] = &[",
    ]
    for vector in vectors:
        pairs = ", ".join(
            f"({_rust_string(name)}, {_rust_string(value)})" for name, value in sorted(vector["environment"].items())
        )
        lines.append(
            "    StorageRootVector { "
            f"name: {_rust_string(vector['name'])}, platform: {_rust_string(vector['platform'])}, "
            f"environment: &[{pairs}], known_folder: {_rust_option(vector['known_folder'])}, "
            f"channel: {_rust_string(vector['channel'])}, expected_root: {_rust_option(vector['expected_root'])}, "
            f"refusal: {_rust_option(vector['refusal'])}, "
            f"invalid_environment: {_rust_strings(vector['invalid_environment'])}, "
            f"invalid_known_folder: {str(vector['invalid_known_folder']).lower()} }},"
        )
    lines.append("];")
    return lines


def _entrypoint_names(layout: dict[str, object]) -> list[str]:
    entrypoints = [
        Path(relative).name for relative in (*entrypoint_files(layout).values(), *bundled_image_files(layout).values())
    ]
    return entrypoints


def _build_contract(root: Path, layout: dict[str, Any], channel: str) -> tuple[dict[str, Any], ApplicationEnvironment]:
    """Resolve authored build inputs and assemble the shared generated contract."""
    declaration = application_environment.load_for_build(root)
    launch = environment_compile.compile_section(declaration, layout)
    release = identity(distribution_target(layout), channel, project_file=root / "pyproject.toml")
    build_channel = release.channel
    version = (root / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    if not version.startswith((root / ".python-version").read_text(encoding="utf-8").strip() + "."):
        raise ValueError("Exact CPython build must belong to the development minor")
    components = declaration.components
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
        "package": _package_section(layout),
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
            "log_file": components["log_file"],
            "manager_log_file": components["manager_log_file"],
            "log_format": components["log_format"],
            "log_max_bytes": components["log_max_bytes"],
            "log_backups": components["log_backups"],
            "output_language": components["language_default"],
            "output_language_variable": components["language_variable"],
            "profile_variable": components["profile_variable"],
        },
    }

    return contract, declaration


MANAGER_STRINGS_FILE = "manager-chrome.json"
"""The manager's localized strings, projected from the locale catalogues apart from the contract."""


def project_manager_strings(destination: Path) -> Path:
    """Write the manager's localized strings, the one part of the contract the locale tooling owns.

    The projection executes the locale tooling, whose import closure is far
    wider than the contract's own, so it is its own cached action: an edit in
    that closure that leaves the strings unchanged leaves the contract, and
    everything compiled from it, current.
    """
    from dev.locales.manager_chrome import manager_chrome_strings

    destination.mkdir(parents=True, exist_ok=True)
    output = destination / MANAGER_STRINGS_FILE
    write_text(output, json.dumps(manager_chrome_strings(), ensure_ascii=False, sort_keys=True) + "\n")
    return output


def _manager_strings(source: Path | None) -> Mapping[str, Mapping[str, str]]:
    if source is None:
        from dev.locales.manager_chrome import manager_chrome_strings

        return manager_chrome_strings()
    document = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("manager strings must be a language-to-strings object")
    result: dict[str, dict[str, str]] = {}
    for language, entries in document.items():
        if not isinstance(language, str) or not isinstance(entries, dict):
            raise ValueError("manager strings must map languages to string objects")
        values: dict[str, str] = {}
        for key, value in entries.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("manager strings must contain only string keys and values")
            values[key] = value
        result[language] = values
    return result


def generate(
    root: Path,
    destination: Path,
    channel: str = "stable",
    *,
    target: str | None = None,
    manager_strings: Path | None = None,
) -> None:
    """Write C, Rust and inspection projections from their authored owners in one run.

    ``channel`` is the release channel the identity projection validated for this build.
    ``manager_strings`` is a :func:`project_manager_strings` output; without it the
    strings are projected in this process.
    """
    layout = load_layout(target, root=root)
    contract, declaration = _build_contract(root, layout, channel)
    components, temporary = declaration.components, declaration.temporary_member
    version = contract["python"]
    launch = contract["application_environment"]
    package_strings = {
        **{key.upper(): value for key, value in layout["paths"].items()},
        "TEMPORARY_MEMBER": temporary["default"],
    }
    rust = [
        f"pub const ABI: u32 = {layout['abi']};",
        f"pub const DEFAULT_ORCHESTRATION_TIMEOUT_SECONDS: u64 = {int(DEFAULT_TIMEOUT_POLICY.timeout_seconds)};",
    ]
    discovery = {"layout": layout, "installation_identity": contract["installation_identity"]}
    rust.append(f"pub const INSTALLATION_CONTRACT: &str = {_rust_string(json.dumps(discovery))};")
    rust.extend(
        [
            f"pub const MANAGER_LOG: &str = {_rust_string(components['manager_log_file'])};",
            f"pub const MANAGER_PREFERENCES: &str = {_rust_string(components['manager_preferences'])};",
            f"pub const MANAGER_FAILED_VERSIONS: &str = {_rust_string(components['manager_failed_versions'])};",
            f"pub const MANAGER_LANGUAGE_ENV: &str = {_rust_string(components['language_variable'])};",
            f"pub const MANAGER_LANGUAGE_DEFAULT: &str = {_rust_string(components['language_default'])};",
            f"pub const LOCAL_AI_ADDRESS: &str = {_rust_string(components['local_ai_address'])};",
            "pub const MANAGER_STRINGS_JSON: &str = "
            f"{_rust_string(json.dumps(_manager_strings(manager_strings), ensure_ascii=False, sort_keys=True))};",
            f"pub const LOG_MAX_BYTES: u64 = {contract['desktop_defaults']['log_max_bytes']};",
            f"pub const LOG_BACKUPS: u32 = {contract['desktop_defaults']['log_backups']};",
        ]
    )
    rust.extend(f"pub const {key}: &str = {_rust_string(value)};" for key, value in package_strings.items())
    # Declared entrypoint images live in NATIVE; the platform context maps them back to the package root.
    entrypoints = _entrypoint_names(layout)
    rust.append(f"pub const ENTRYPOINT_FILES: &[&str] = {_rust_strings(entrypoints)};")
    rust.extend(_rust_root_and_environment(contract))
    rust.extend(rust_transport(contract["runtime_transport"]))
    rust.extend(rust_runtime_exit_reasons(contract["runtime_exit"]))
    rust.extend(environment_compile.rust_lines(launch))
    destination.mkdir(parents=True, exist_ok=True)
    write_text(destination / "contract.rs", "\n".join(rust) + "\n")
    write_text(
        destination / "contract.h",
        f'#define CADRUMO_PYTHON_VERSION "{version}"\n#define CADRUMO_PLATFORM_ABI {layout["abi"]}\n'
        f"#define CADRUMO_CONTRACT_SCHEMA {CONTRACT_SCHEMA}\n"
        + "".join(f"{line}\n" for line in environment_compile.c_lines(launch)),
    )
    write_text(destination / "contract.json", json.dumps(contract, indent=2) + "\n")
    root_vectors = [vector.as_contract() for vector in storage_root_vectors(root)]
    vectors = [
        *_rust_root_vectors(root_vectors),
        *environment_compile.rust_vector_lines(environment_compile.vectors_for(declaration, layout)),
    ]
    write_text(destination / "contract_vectors.rs", "\n".join(vectors) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=require_enrolled_output)
    parser.add_argument("--channel", default="stable")
    parser.add_argument("--target")
    parser.add_argument("--manager-strings", type=Path, help="a projected manager strings file to embed")
    parser.add_argument(
        "--project-manager-strings", action="store_true", help="write only the manager strings projection"
    )
    args = parser.parse_args()
    record_discovered_inputs()
    if args.project_manager_strings:
        project_manager_strings(args.destination)
    else:
        generate(
            Path(__file__).resolve().parents[3],
            args.destination,
            args.channel,
            target=args.target,
            manager_strings=args.manager_strings,
        )
