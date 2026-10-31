"""Keep the native contract's storage projection equal to the package declaration and the CLI's own defaults."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OUTPUT_LANGUAGE_ENV_VAR
from cadrumo.core.logging import LOG_FILE_FORMAT
from cadrumo.core.profile_root_environment import PROFILE_ROOT_VARIABLE
from cadrumo.core.storage_environment import (
    STORAGE_PATH_RULES,
    STORAGE_ROOT,
    StoragePlatform,
    StorageRootRefusal,
)
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY
from dev._paths import REPO_ROOT
from dev.locales.manager_chrome import manager_chrome_strings
from dev.packaging.native import generate as generator_module
from dev.packaging.native.application_environment import load
from dev.packaging.native.generate import generate
from dev.packaging.native.layout import load_layout
from dev.packaging.native.release_image_scan import RETIRED_STORAGE_VARIABLES
from dev.packaging.native.storage_vectors import storage_path_vectors, storage_root_vectors
from dev.packaging.native.verification_paths import verification_destination
from dev.tool_storage import TOOL_STORAGE_LOCATIONS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEVELOPMENT_VARIABLES = frozenset(variable for variable, _default in TOOL_STORAGE_LOCATIONS.values())


def _rust_strings(generated: str, constant: str) -> list[str]:
    line = next(line for line in generated.splitlines() if line.startswith(f"pub const {constant}:"))
    return [match.group(1) for match in re.finditer(r'"([^"]*)"', line.partition("= ")[2])]


def test_desktop_defaults_project_the_package_declaration(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))
    components = load(REPO_ROOT).components
    assert contract["desktop_defaults"] == {
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
    }
    # The desktop withholds the profile folder the command line's launchers derive, under the same name.
    assert components["profile_variable"] == PROFILE_ROOT_VARIABLE
    # The desktop reads the command line's log and language without asking Python, so both state the same values.
    assert components["logs"] == STORAGE_TAXONOMY[StorageCategory.LOGS].subpath
    assert components["log_file"] == STORAGE_TAXONOMY[StorageCategory.LOG_FILE].subpath
    assert components["log_format"] == LOG_FILE_FORMAT
    assert components["log_max_bytes"] == Settings.model_fields["cadrumo_log_file_max_bytes"].default
    assert components["log_backups"] == Settings.model_fields["cadrumo_log_file_backup_count"].default
    assert components["language_variable"] == OUTPUT_LANGUAGE_ENV_VAR
    assert components["language_default"] == DEFAULT_OUTPUT_LANGUAGE.value

    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    assert _rust_strings(generated, "MANAGER_LOG") == [components["manager_log_file"]]
    assert _rust_strings(generated, "MANAGER_PREFERENCES") == [components["manager_preferences"]]
    assert _rust_strings(generated, "MANAGER_FAILED_VERSIONS") == [components["manager_failed_versions"]]
    assert _rust_strings(generated, "MANAGER_LANGUAGE_ENV") == [components["language_variable"]]
    assert _rust_strings(generated, "MANAGER_LANGUAGE_DEFAULT") == [components["language_default"]]
    strings = json.dumps(manager_chrome_strings(), ensure_ascii=False, sort_keys=True)
    assert f"pub const MANAGER_STRINGS_JSON: &str = {generator_module._rust_string(strings)};" in generated
    assert f"pub const LOG_MAX_BYTES: u64 = {components['log_max_bytes']};" in generated
    assert f"pub const LOG_BACKUPS: u32 = {components['log_backups']};" in generated


def test_native_contract_names_the_one_storage_root_and_no_allowlist_or_location(tmp_path: Path) -> None:
    destination = tmp_path / "generated"
    generate(REPO_ROOT, destination)
    declaration = load(REPO_ROOT)

    contract = json.loads((destination / "contract.json").read_text(encoding="utf-8"))
    generated = (destination / "contract.rs").read_text(encoding="utf-8")
    assert "locations" not in declaration.groups
    assert [name for name, entry in declaration.names.items() if entry["role"] == "location"] == [
        declaration.root["variable"]
    ]
    assert "location_names" not in contract["application_environment"]
    assert declaration.root["variable"] not in _DEVELOPMENT_VARIABLES
    for retired in ("PRODUCT_ENV_ALLOWLIST", "PACKAGE_ENV_ALLOWLIST", "RESERVED_ENV"):
        assert f"pub const {retired}:" not in generated
    assert "storage_environment_allowlist" not in contract
    assert "overrides" not in contract["layout"]

    temporary = declaration.temporary_member
    assert set(temporary) == {"default"}
    assert f'pub const TEMPORARY_MEMBER: &str = "{temporary["default"]}";' in generated
    assert "TEMPORARY_ENV" not in generated and "TEMPORARY_CREATE_EXPLICIT" not in generated
    # The command line places its temporary files at the same member beneath the root.
    assert temporary["default"] == STORAGE_TAXONOMY[StorageCategory.TEMPORARY_FILES].relative_path().as_posix()


def test_native_verification_stage_is_under_its_declared_output_root(tmp_path: Path) -> None:
    build_root = tmp_path / "build"
    build_root.mkdir()

    default = verification_destination(None, build_root)
    relative = verification_destination(Path("verification/package-one"), build_root)
    assert default.is_relative_to(build_root.resolve())
    assert relative == build_root.resolve() / "verification" / "package-one"
    with pytest.raises(ValueError, match="beneath its owning build output directory"):
        verification_destination(tmp_path / "external-package", build_root)
    with pytest.raises(ValueError, match="beneath its owning build output directory"):
        verification_destination(Path("../outside"), build_root)


def test_schema_one_contract_projects_the_storage_declaration(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    declaration = load(REPO_ROOT)

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
    # Every image carries the one storage rule; a Debug build's root is baked in by CMake.
    assert set(root) == set(declaration.root)
    assert not {"precedence", "relative_override", "development_variable", "development_default"} & set(root)
    # The command line keeps its own built-in rule for runs outside a package; both state the same rule.
    assert root["variable"] == STORAGE_ROOT.variable
    assert root["path_rules"] == STORAGE_PATH_RULES._asdict()
    assert root["refusals"] == [refusal.value for refusal in StorageRootRefusal]
    assert root["posix_directory_mode"] == STORAGE_ROOT.posix_directory_mode
    for platform in StoragePlatform:
        rule = STORAGE_ROOT.installed_rule(platform)
        declared = next(item for item in root["installed_defaults"] if item["platform"] == platform.value)
        assert declared == {
            "platform": platform.value,
            "candidates": [
                {"variable": candidate.variable, "subpath": list(candidate.subpath)} for candidate in rule.candidates
            ],
            "home_variable": rule.home_variable,
        }
    for refusal in root["refusals"]:
        assert _rust_strings(generated, f"ROOT_REFUSAL_{refusal.upper()}") == [refusal]

    environment = contract["environment"]
    assert environment["pinned"] == [root["variable"], *declaration.temporary]
    assert environment["host_inherited"]["fields"] == [{"name": declaration.authority.name, "kind": "directory_path"}]
    layout = load_layout()
    assert "mode" not in contract
    assert contract["package"] == {
        "package_manifest": layout["files"]["package_manifest"],
        "package_root_from_executable": layout["package_root_from_executable"],
    }
    assert "vectors" not in contract
    assert contract["path_vectors"] == [vector.as_contract() for vector in storage_path_vectors()]
    assert "member_vectors" not in contract
    assert contract["invalid_native_path"]["refusal"] == StorageRootRefusal.INVALID_PATH_INPUT.value

    # contract.rs carries the same data from the same run.
    assert _rust_strings(generated, "ROOT_VARIABLE") == [root["variable"]]
    assert "INSTALLED_ROOT_PRECEDENCE" not in generated and "INSTALLED_RELATIVE_OVERRIDE" not in generated
    assert _rust_strings(generated, "PINNED_ENV") == environment["pinned"]
    assert _rust_strings(generated, "PACKAGE_MANIFEST") == [contract["package"]["package_manifest"]]
    assert "MODE_PACKAGE" not in generated and "BUILD_STORAGE_ROOT" not in generated
    # The resolver's test vectors live apart from the contract every image includes.
    vectors = (tmp_path / "contract_vectors.rs").read_text(encoding="utf-8")
    rust_vectors = re.findall(r'StorageRootVector \{ name: "([^"]+)"', vectors)
    assert rust_vectors == [vector.name for vector in storage_root_vectors(REPO_ROOT)] and rust_vectors
    assert "StorageRootVector" not in generated and "StorageMemberVector" not in generated
    # The launch conformance vectors are test inputs too: no packaged contract carries them.
    assert "LAUNCH_VECTORS" not in generated and "LAUNCH_VECTORS" in vectors
    assert "vectors" not in contract["application_environment"]


def test_packaged_contract_carries_no_development_storage_rule_or_retired_variable(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    development = ("var/storage", "var\\storage", "pyproject.toml", *RETIRED_STORAGE_VARIABLES)
    for name in ("contract.rs", "contract.json", "contract.h"):
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert not [spelling for spelling in development if spelling in text], name


def test_packaged_contract_carries_no_development_tool_location(tmp_path: Path) -> None:
    generate(REPO_ROOT, tmp_path)
    generated = (tmp_path / "contract.rs").read_text(encoding="utf-8")
    installed_bases = {candidate.variable for rule in STORAGE_ROOT.installed_defaults for candidate in rule.candidates}
    tool_names = _DEVELOPMENT_VARIABLES | (set(TOOL_STORAGE_LOCATIONS) - installed_bases)
    assert not {name for name in tool_names if f'"{name}"' in generated}
    for retired in ("TOOL_CACHE_ENV", "TOOL_CACHE_DEFAULT", "STORAGE_ENV_ALLOWLIST", "STORAGE_ROOT_ENV"):
        assert f"pub const {retired}:" not in generated
    contract = json.loads((tmp_path / "contract.json").read_text(encoding="utf-8"))
    assert "locations" not in contract and "settings" not in contract and "storage" not in contract


_ENVIRONMENT_NAME: re.Pattern[str] = re.compile(r"[A-Z][A-Z0-9_]+")


def _location_variable_names() -> frozenset[str]:
    declaration = load(REPO_ROOT)
    return frozenset(
        str(name)
        for name in {
            STORAGE_ROOT.variable,
            *RETIRED_STORAGE_VARIABLES,
            *declaration.temporary,
            declaration.authority.name,
            *_DEVELOPMENT_VARIABLES,
        }
    )


def _spelled_location_names(source: str) -> set[str]:
    return {match[0] for match in _ENVIRONMENT_NAME.finditer(source)} & _location_variable_names()


def test_generator_spells_no_location_variable_name() -> None:
    planted = 'strings = {"STORAGE_ENV": "CADRUMO_LOCAL_STORAGE_ROOT", "ROOT": "CADRUMO_STORAGE_ROOT"}'
    assert _spelled_location_names(planted) == {"CADRUMO_LOCAL_STORAGE_ROOT", "CADRUMO_STORAGE_ROOT"}
    source = Path(generator_module.__file__).read_text(encoding="utf-8")
    assert _spelled_location_names(source) == set()
    assert "var/storage" not in source
