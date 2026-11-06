"""The window projections have one location, and every consumer that spells it agrees with the enrolled presets."""

from __future__ import annotations

import json
import re

import pytest

from ..._paths import REPO_ROOT
from ..location import HOST_PRESETS, WINDOW_BELOW_BUILD, host_preset, window_projections
from ..registry import FAMILIES

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"


def _enrolled_presets() -> set[str]:
    document = json.loads((REPO_ROOT / "CMakePresets.json").read_text(encoding="utf-8"))
    return {preset["name"] for preset in document["configurePresets"]}


def test_every_host_preset_is_an_enrolled_configure_preset() -> None:
    assert set(HOST_PRESETS.values()) <= _enrolled_presets()


def test_the_projection_directory_is_the_host_presets_build_tree() -> None:
    assert window_projections() == f"build/{host_preset()}/{WINDOW_BELOW_BUILD}"


def test_the_typescript_alias_names_every_host_presets_projection_directory() -> None:
    configuration = (_FRONTEND / "tsconfig.json").read_text(encoding="utf-8")
    declared = json.loads(configuration)["compilerOptions"]["paths"]["@fixtures/*"]
    assert declared == [f"../../../build/{preset}/{WINDOW_BELOW_BUILD}/*" for preset in HOST_PRESETS.values()]


def test_the_frontend_scripts_map_each_host_to_the_same_preset() -> None:
    source = (_FRONTEND / "scripts" / "fixture-paths.mjs").read_text(encoding="utf-8")
    spelled = set(re.findall(r'"[a-z0-9]+:[a-z0-9]+": "([a-z0-9-]+)"', source))
    assert spelled == set(HOST_PRESETS.values())


def test_the_cmake_environment_names_the_same_presets() -> None:
    source = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    spelled = set(re.findall(r"set\(cadrumo_fixture_preset ([a-z0-9-]+)\)", source))
    assert spelled == set(HOST_PRESETS.values())


def test_a_generated_window_family_writes_inside_the_projection_directory() -> None:
    generated = [family for family in FAMILIES if family.producer is not None and not family.committed]
    assert generated
    for family in generated:
        assert family.output_root == window_projections(), family.name
