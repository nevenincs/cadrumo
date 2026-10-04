"""Project canonical Python declarations into native build inputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cadrumo.core.config import Settings
from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.storage_environment import TOOL_STORAGE_LOCATIONS, configured_storage_root
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY

from .layout import entrypoint_files, load_layout


def generate(root: Path, destination: Path) -> None:
    """Write C, Rust and inspection projections from their authored owners."""
    layout = load_layout(root=root)
    version = (root / "dev/packaging/release-python-version").read_text(encoding="utf-8").strip()
    if not version.startswith((root / ".python-version").read_text(encoding="utf-8").strip() + "."):
        raise ValueError("Exact CPython build must belong to the development minor")
    fields = sorted(name.upper() for name in Settings.model_fields)
    tool_cache_env, tool_cache_default = TOOL_STORAGE_LOCATIONS["XDG_CACHE_HOME"]
    storage_envs = set(Settings.storage_env_var_names())
    if tool_cache_env not in storage_envs:
        raise ValueError(f"Tool storage environment name is missing from Settings contract: {tool_cache_env}")
    for location in STORAGE_TAXONOMY.values():
        field = location.settings_field
        if field is None:
            continue
        if field not in Settings.model_fields:
            raise ValueError(f"Storage taxonomy field is missing from Settings: {field}")
        if field.upper() not in storage_envs:
            raise ValueError(f"Storage taxonomy environment name is missing from Settings contract: {field.upper()}")
    temporary = STORAGE_TAXONOMY[StorageCategory.TEMPORARY_FILES]
    if temporary.settings_field is None:
        raise ValueError("Temporary storage must declare its Settings field")
    paths = layout["paths"]
    destination.mkdir(parents=True, exist_ok=True)
    rust = [f"pub const ABI: u32 = {layout['abi']};"]
    strings = {
        **{key.upper(): value for key, value in paths.items()},
        "PRODUCT_NAME": PRODUCT_IDENTITY.python_package,
        "STORAGE_ENV": "CADRUMO_LOCAL_STORAGE_ROOT",
        "STORAGE_ROOT_ENV": "CADRUMO_STORAGE_ROOT",
        "STORAGE_DEFAULT": configured_storage_root(environ={}, repository_root=root)
        .relative_to(root.resolve())
        .as_posix(),
        "AUTHORITY_ENV": "cadrumo_authority_root".upper(),
        "TEMPORARY_ENV": temporary.settings_field.upper(),
        "TEMPORARY_DEFAULT": temporary.relative_path().as_posix(),
        "TOOL_CACHE_ENV": tool_cache_env,
        "TOOL_CACHE_DEFAULT": tool_cache_default,
    }
    for name in ("cadrumo_local_storage_root", "cadrumo_authority_root"):
        if name not in Settings.model_fields:
            raise ValueError(f"Missing Settings owner: {name}")
    rust.extend(f"pub const {key}: &str = {json.dumps(value)};" for key, value in strings.items())
    rust.append("pub const RESERVED_ENV: &[&str] = &[" + ",".join(map(json.dumps, fields)) + "];")
    rust.append(
        "pub const STORAGE_ENV_ALLOWLIST: &[&str] = &[" + ",".join(map(json.dumps, sorted(storage_envs))) + "];"
    )
    rust.append("pub const PACKAGE_ENV_ALLOWLIST: &[&str] = &[" + ",".join(map(json.dumps, layout["overrides"])) + "];")
    # Declared entrypoint images live in NATIVE; the platform context maps them back to the package root.
    entrypoints = [Path(relative).name for relative in entrypoint_files(layout).values()]
    rust.append("pub const ENTRYPOINT_FILES: &[&str] = &[" + ",".join(map(json.dumps, entrypoints)) + "];")
    (destination / "contract.rs").write_text("\n".join(rust) + "\n", encoding="utf-8")
    (destination / "contract.h").write_text(
        f'#define CADRUMO_PYTHON_VERSION "{version}"\n#define CADRUMO_PLATFORM_ABI {layout["abi"]}\n',
        encoding="utf-8",
    )
    contract = {
        "layout": layout,
        "python": version,
        "settings": fields,
        "storage_environment_allowlist": sorted(storage_envs),
        "storage": [item.model_dump(mode="json") for item in STORAGE_TAXONOMY.values()],
    }
    (destination / "contract.json").write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    generate(Path(__file__).resolve().parents[3], args.destination)
