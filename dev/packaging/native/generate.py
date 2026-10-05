"""Project canonical Python declarations into native build inputs."""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from cadrumo.core.config import AuthorityRootSettings, Settings
from cadrumo.core.storage_environment import (
    PROCESS_ENVIRONMENT,
    STORAGE_ROOT,
    ChildEnvironmentProfile,
    StorageMode,
    StorageRootRefusal,
    development_tool_env_var_names,
    product_env_var_names,
)
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY

from .identity import identity
from .layout import distribution_target, entrypoint_files, load_layout
from .runtime_exit_reasons import runtime_exit_section, rust_runtime_exit_reasons
from .storage_vectors import storage_root_vectors

CONTRACT_SCHEMA = 1


def _rust_string(value: str) -> str:
    literal = json.dumps(value, ensure_ascii=False)
    if "\\u" in literal:
        raise ValueError(f"Contract string needs an escape Rust does not share with JSON: {value!r}")
    return literal


def _rust_strings(values: Iterable[str]) -> str:
    return "&[" + ",".join(map(_rust_string, values)) + "]"


def _rust_option(value: str | None) -> str:
    return "None" if value is None else f"Some({_rust_string(value)})"


def _require_authority_pin() -> None:
    """The native host pins only the Settings-owned authority root beyond the pinned set."""
    for variable in (*PROCESS_ENVIRONMENT.host_inherited, *PROCESS_ENVIRONMENT.windows_host_inherited):
        if variable.lower() not in AuthorityRootSettings.model_fields:
            raise ValueError(f"Host-inherited pin is not the authority root setting: {variable}")


def _root_section() -> dict[str, Any]:
    return {
        "variable": STORAGE_ROOT.variable,
        "development_variable": STORAGE_ROOT.development_variable,
        "precedence": {mode.value: list(STORAGE_ROOT.root_variables(mode)) for mode in StorageMode},
        "development_default": "/".join(STORAGE_ROOT.development_default),
        "installed_defaults": [
            {
                "platform": rule.platform.value,
                "candidates": [
                    {"variable": candidate.variable, "subpath": list(candidate.subpath)}
                    for candidate in rule.candidates
                ],
                "home_variable": rule.home_variable,
            }
            for rule in STORAGE_ROOT.installed_defaults
        ],
        "channel": {
            "product_directory": STORAGE_ROOT.product_directory,
            "stable": STORAGE_ROOT.stable_channel,
            "separator": STORAGE_ROOT.channel_separator,
        },
        "relative_override": {mode.value: STORAGE_ROOT.relative_override(mode).value for mode in StorageMode},
        "blank_is_unset": True,
        "posix_directory_mode": STORAGE_ROOT.posix_directory_mode,
        "refusals": [refusal.value for refusal in StorageRootRefusal],
    }


def _locations_section() -> list[dict[str, Any]]:
    return [
        {
            "category": location.category.value,
            "subpath": location.subpath,
            "variable": None if location.settings_field is None else location.settings_field.upper(),
            "override_policy": location.override_policy.value,
            "scope": location.scope.value,
            "node_kind": location.node_kind.value,
            "grouping": location.grouping.value,
            "lifecycle": location.lifecycle.value,
        }
        for location in STORAGE_TAXONOMY.values()
    ]


def _environment_section(fields: list[str]) -> dict[str, Any]:
    declaration = PROCESS_ENVIRONMENT
    return {
        "cleared": {
            "prefixes": list(declaration.cleared_prefixes),
            "names": list(declaration.cleared_names),
            "namespace_prefix": declaration.namespace_prefix,
            "reserved_settings": fields,
        },
        "pinned": [STORAGE_ROOT.variable, *declaration.temporary_variables],
        "host_inherited": {
            "all": list(declaration.host_inherited),
            "windows": list(declaration.windows_host_inherited),
        },
        "allowlist": {
            "product": sorted(product_env_var_names()),
            "development": sorted({STORAGE_ROOT.development_variable, *development_tool_env_var_names()}),
        },
        "profiles": {
            ChildEnvironmentProfile.OPERATOR.value: {"passes_product_allowlist": True},
            ChildEnvironmentProfile.STRICT.value: {"passes_product_allowlist": False},
        },
    }


def _mode_section(layout: dict[str, Any]) -> dict[str, Any]:
    return {
        "package_manifest": layout["files"]["package_manifest"],
        "package_root_from_executable": layout["package_root_from_executable"],
        "checkout_marker": STORAGE_ROOT.checkout_marker,
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
        f"pub const PRODUCT_ENV_ALLOWLIST: &[&str] = {_rust_strings(environment['allowlist']['product'])};",
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
            f"refusal: {_rust_option(vector['refusal'])} }},"
        )
    lines.append("];")
    return lines


def generate(root: Path, destination: Path, channel: str = "stable") -> None:
    """Write C, Rust and inspection projections from their authored owners in one run.

    ``channel`` is the release channel the identity projection validated for this build.
    """
    layout = load_layout(root=root)
    build_channel = identity(distribution_target(layout), channel, project_file=root / "pyproject.toml").channel
    version = (root / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    if not version.startswith((root / ".python-version").read_text(encoding="utf-8").strip() + "."):
        raise ValueError("Exact CPython build must belong to the development minor")
    fields = sorted(name.upper() for name in Settings.model_fields)
    product = product_env_var_names()
    if Settings.storage_env_var_names() != product:
        raise ValueError("Settings launch allowlist must equal the product allowlist")
    for location in STORAGE_TAXONOMY.values():
        field = location.settings_field
        if field is None:
            continue
        if field not in Settings.model_fields:
            raise ValueError(f"Storage taxonomy field is missing from Settings: {field}")
    if STORAGE_ROOT.variable.lower() not in Settings.model_fields:
        raise ValueError(f"Storage root variable has no Settings owner: {STORAGE_ROOT.variable}")
    temporary = STORAGE_TAXONOMY[StorageCategory.TEMPORARY_FILES]
    if temporary.settings_field is None:
        raise ValueError("Temporary storage must declare its Settings field")
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "channel": {"build": build_channel, "installed_directory": STORAGE_ROOT.channel_directory(build_channel)},
        "layout": layout,
        "python": version,
        "settings": fields,
        "storage_environment_allowlist": sorted(product),
        "storage": [item.model_dump(mode="json") for item in STORAGE_TAXONOMY.values()],
        "root": _root_section(),
        "locations": _locations_section(),
        "environment": _environment_section(fields),
        "mode": _mode_section(layout),
        "vectors": [vector.as_contract() for vector in storage_root_vectors()],
        "runtime_exit": runtime_exit_section(),
    }
    _require_authority_pin()
    package_strings = {
        **{key.upper(): value for key, value in layout["paths"].items()},
        "TEMPORARY_ENV": temporary.settings_field.upper(),
        "TEMPORARY_DEFAULT": temporary.relative_path().as_posix(),
    }
    rust = [f"pub const ABI: u32 = {layout['abi']};"]
    rust.extend(f"pub const {key}: &str = {_rust_string(value)};" for key, value in package_strings.items())
    rust.append(f"pub const RESERVED_ENV: &[&str] = {_rust_strings(fields)};")
    rust.append(f"pub const PACKAGE_ENV_ALLOWLIST: &[&str] = {_rust_strings(layout['overrides'])};")
    # Declared entrypoint images live in NATIVE; the platform context maps them back to the package root.
    entrypoints = [Path(relative).name for relative in entrypoint_files(layout).values()]
    rust.append(f"pub const ENTRYPOINT_FILES: &[&str] = {_rust_strings(entrypoints)};")
    rust.extend(_rust_root_and_environment(contract))
    rust.extend(rust_runtime_exit_reasons(contract["runtime_exit"]))
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "contract.rs").write_text("\n".join(rust) + "\n", encoding="utf-8")
    (destination / "contract.h").write_text(
        f'#define CADRUMO_PYTHON_VERSION "{version}"\n#define CADRUMO_PLATFORM_ABI {layout["abi"]}\n'
        f"#define CADRUMO_CONTRACT_SCHEMA {CONTRACT_SCHEMA}\n",
        encoding="utf-8",
    )
    (destination / "contract.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--channel", default="stable")
    args = parser.parse_args()
    generate(Path(__file__).resolve().parents[3], args.destination, args.channel)
