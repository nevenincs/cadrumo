"""Keep the native bootstrap's storage environment projection in taxonomy parity."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cadrumo.core.config import Settings
from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import STORAGE_TAXONOMY
from dev._paths import REPO_ROOT
from dev.packaging.native.generate import generate
from dev.packaging.native.verify import _verification_destination

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_native_storage_allowlist_tracks_settings_taxonomy_and_tool_paths(tmp_path: Path) -> None:
    destination = tmp_path / "generated"
    generate(REPO_ROOT, destination)

    contract = json.loads((destination / "contract.json").read_text(encoding="utf-8"))
    generated = (destination / "contract.rs").read_text(encoding="utf-8")
    declaration = next(line for line in generated.splitlines() if line.startswith("pub const STORAGE_ENV_ALLOWLIST"))
    rust_values = declaration.partition("= &[")[2].partition("];")[0]
    observed = tuple(re.findall(r'"([^"]+)"', rust_values))
    expected = tuple(sorted(Settings.storage_env_var_names()))
    assert observed == expected == tuple(contract["storage_environment_allowlist"])
    assert "CADRUMO_STRICT_SECURITY" not in observed

    temporary = STORAGE_TAXONOMY[StorageCategory.TEMPORARY_FILES]
    assert temporary.settings_field is not None
    assert f'pub const TEMPORARY_ENV: &str = "{temporary.settings_field.upper()}";' in generated
    assert f'pub const TEMPORARY_DEFAULT: &str = "{temporary.relative_path().as_posix()}";' in generated


def test_native_verification_stage_is_under_the_refined_build_root(tmp_path: Path) -> None:
    build_root = tmp_path / "build"
    build_root.mkdir()

    default = _verification_destination(None, build_root)
    relative = _verification_destination(Path("verification/package-one"), build_root)
    assert default.is_relative_to(build_root.resolve())
    assert relative == build_root.resolve() / "verification" / "package-one"
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    explicit_absolute = _verification_destination(
        tmp_path / "external-package",
        build_root,
        repository_root=checkout,
    )
    assert explicit_absolute == tmp_path / "external-package"
    with pytest.raises(ValueError, match="CADRUMO_NATIVE_BUILD_ROOT"):
        _verification_destination(Path("../outside"), build_root)
