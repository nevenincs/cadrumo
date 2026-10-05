"""Keep the native bootstrap's storage environment projection in taxonomy parity."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.storage_environment import (
    PROCESS_ENVIRONMENT,
    STORAGE_ROOT,
    TOOL_STORAGE_LOCATIONS,
    StorageMode,
    development_tool_env_var_names,
    product_env_var_names,
)
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY
from dev._paths import REPO_ROOT
from dev.packaging.native import generate as generator_module
from dev.packaging.native.generate import generate
from dev.packaging.native.layout import load_layout
from dev.packaging.native.storage_vectors import storage_root_vectors
from dev.packaging.native.verification_paths import verification_destination

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_native_storage_allowlist_tracks_settings_taxonomy_and_tool_paths(tmp_path: Path) -> None:
    destination = tmp_path / "generated"
    generate(REPO_ROOT, destination)

    contract = json.loads((destination / "contract.json").read_text(encoding="utf-8"))
    generated = (destination / "contract.rs").read_text(encoding="utf-8")
    declaration = next(line for line in generated.splitlines() if line.startswith("pub const PRODUCT_ENV_ALLOWLIST"))
    rust_values = declaration.partition("= &[")[2].partition("];")[0]
    observed = tuple(re.findall(r'"([^"]+)"', rust_values))
    expected = tuple(sorted(Settings.storage_env_var_names()))
    assert observed == expected == tuple(contract["storage_environment_allowlist"])
    assert expected == tuple(sorted(product_env_var_names()))
    assert not set(observed) & development_tool_env_var_names()
    assert "CADRUMO_STRICT_SECURITY" not in observed

    temporary = STORAGE_TAXONOMY[StorageCategory.TEMPORARY_FILES]
    assert temporary.settings_field is not None
    assert f'pub const TEMPORARY_ENV: &str = "{temporary.settings_field.upper()}";' in generated
    assert f'pub const TEMPORARY_DEFAULT: &str = "{temporary.relative_path().as_posix()}";' in generated


def test_native_verification_stage_is_under_the_refined_build_root(tmp_path: Path) -> None:
    build_root = tmp_path / "build"
    build_root.mkdir()

    default = verification_destination(None, build_root)
    relative = verification_destination(Path("verification/package-one"), build_root)
    assert default.is_relative_to(build_root.resolve())
    assert relative == build_root.resolve() / "verification" / "package-one"
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    explicit_absolute = verification_destination(
        tmp_path / "external-package",
        build_root,
        repository_root=checkout,
    )
    assert explicit_absolute == tmp_path / "external-package"
    with pytest.raises(ValueError, match="CADRUMO_NATIVE_BUILD_ROOT"):
        verification_destination(Path("../outside"), build_root)


def _rust_strings(generated: str, constant: str) -> list[str]:
    line = next(line for line in generated.splitlines() if line.startswith(f"pub const {constant}:"))
    return [match.group(1) for match in re.finditer(r'"([^"]*)"', line.partition("= ")[2])]


def test_schema_one_contract_projects_the_storage_declaration(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")

    assert contract["schema"] == 1
    assert "#define CADRUMO_CONTRACT_SCHEMA 1" in (tmp_path / "contract.h").read_text(encoding="utf-8")
    assert contract["channel"] == {"build": "stable", "installed_directory": STORAGE_ROOT.product_directory}
    assert _rust_strings(generated, "BUILD_CHANNEL") == ["stable"]
    preview = tmp_path / "preview"
    generate(REPO_ROOT, preview, "preview")
    preview_contract = json.loads((preview / "contract.json").read_text(encoding="utf-8"))
    assert preview_contract["channel"] == {
        "build": "preview",
        "installed_directory": STORAGE_ROOT.channel_directory("preview"),
    }
    with pytest.raises(ValueError, match="Unsupported release channel"):
        generate(REPO_ROOT, tmp_path / "unknown", "nightly")
    root = contract["root"]
    assert root["variable"] == STORAGE_ROOT.variable
    assert root["precedence"] == {
        "development": [STORAGE_ROOT.variable, STORAGE_ROOT.development_variable],
        "installed": [STORAGE_ROOT.variable],
    }
    assert root["development_default"] == Path(*STORAGE_ROOT.development_default).as_posix()
    assert root["relative_override"] == {mode.value: STORAGE_ROOT.relative_override(mode).value for mode in StorageMode}
    assert {rule["platform"] for rule in root["installed_defaults"]} == {"windows", "linux", "macos"}
    windows = next(rule for rule in root["installed_defaults"] if rule["platform"] == "windows")
    assert windows["candidates"] == [{"variable": "LOCALAPPDATA", "subpath": []}]

    locations = {entry["category"]: entry for entry in contract["locations"]}
    assert set(locations) == {category.value for category in STORAGE_TAXONOMY}
    for category, location in STORAGE_TAXONOMY.items():
        entry = locations[category.value]
        assert entry["subpath"] == location.subpath
        expected_variable = None if location.settings_field is None else location.settings_field.upper()
        assert entry["variable"] == expected_variable
        assert entry["override_policy"] == location.override_policy.value

    environment = contract["environment"]
    assert environment["pinned"] == [STORAGE_ROOT.variable, *PROCESS_ENVIRONMENT.temporary_variables]
    assert environment["allowlist"]["product"] == sorted(product_env_var_names())
    assert environment["allowlist"]["development"] == sorted(
        {STORAGE_ROOT.development_variable, *development_tool_env_var_names()}
    )
    assert not set(environment["allowlist"]["product"]) & set(environment["allowlist"]["development"])
    assert STORAGE_ROOT.development_variable not in environment["allowlist"]["product"]
    assert STORAGE_ROOT.development_variable not in _rust_strings(generated, "PRODUCT_ENV_ALLOWLIST")
    assert environment["profiles"] == {
        "operator": {"passes_product_allowlist": True},
        "strict": {"passes_product_allowlist": False},
    }
    layout = load_layout()
    assert contract["mode"] == {
        "package_manifest": layout["files"]["package_manifest"],
        "package_root_from_executable": layout["package_root_from_executable"],
        "checkout_marker": STORAGE_ROOT.checkout_marker,
    }
    assert contract["vectors"] == [vector.as_contract() for vector in storage_root_vectors()]
    assert len(contract["vectors"]) >= 1

    # contract.rs carries the same data from the same run.
    assert _rust_strings(generated, "ROOT_VARIABLE") == [STORAGE_ROOT.variable]
    assert _rust_strings(generated, "INSTALLED_ROOT_PRECEDENCE") == root["precedence"]["installed"]
    assert _rust_strings(generated, "PINNED_ENV") == environment["pinned"]
    assert _rust_strings(generated, "PRODUCT_ENV_ALLOWLIST") == environment["allowlist"]["product"]
    assert _rust_strings(generated, "MODE_PACKAGE_MANIFEST") == [contract["mode"]["package_manifest"]]
    rust_vectors = re.findall(r'StorageRootVector \{ name: "([^"]+)"', generated)
    assert rust_vectors == [vector["name"] for vector in contract["vectors"]]


def test_packaged_contract_carries_no_development_tool_location(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    installed_bases = {candidate.variable for rule in STORAGE_ROOT.installed_defaults for candidate in rule.candidates}
    tool_names = development_tool_env_var_names() | (set(TOOL_STORAGE_LOCATIONS) - installed_bases)
    assert not {name for name in tool_names if f'"{name}"' in generated}
    for retired in ("TOOL_CACHE_ENV", "TOOL_CACHE_DEFAULT", "STORAGE_ENV_ALLOWLIST", "STORAGE_ROOT_ENV"):
        assert f"pub const {retired}:" not in generated
    locations = {
        entry["category"]: entry for entry in json.loads((tmp_path / "contract.json").read_text())["locations"]
    }
    cache = locations[StorageCategory.PYWIN32_GENERATED_CACHE.value]
    assert (cache["subpath"], cache["variable"], cache["override_policy"]) == (
        STORAGE_TAXONOMY[StorageCategory.PYWIN32_GENERATED_CACHE].subpath,
        None,
        "fixed",
    )


_ENVIRONMENT_NAME: re.Pattern[str] = re.compile(r"[A-Z][A-Z0-9_]+")


def _location_variable_names() -> frozenset[str]:
    taxonomy = {location.settings_field.upper() for location in STORAGE_TAXONOMY.values() if location.settings_field}
    return frozenset({*STORAGE_ROOT.precedence, *taxonomy, *product_env_var_names(), *development_tool_env_var_names()})


def _spelled_location_names(source: str) -> set[str]:
    return {match[0] for match in _ENVIRONMENT_NAME.finditer(source)} & _location_variable_names()


def test_generator_spells_no_location_variable_name() -> None:
    planted = 'strings = {"STORAGE_ENV": "CADRUMO_LOCAL_STORAGE_ROOT"}'
    assert _spelled_location_names(planted) == {"CADRUMO_LOCAL_STORAGE_ROOT"}
    source = Path(generator_module.__file__).read_text(encoding="utf-8")
    assert _spelled_location_names(source) == set()
    assert "var/storage" not in source
