"""The window projections have one location, and every consumer that spells it agrees with the enrolled presets."""

from __future__ import annotations

import json
import re

import pytest

from ...paths import REPO_ROOT
from ..location import HOST_PRESETS, WINDOW_BELOW_BUILD, host_preset, window_projections
from ..registry import FAMILIES, window_families

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


def test_the_window_selection_is_every_generated_window_family_and_no_committed_one() -> None:
    selected = window_families()
    assert selected
    assert all(family.output_root == window_projections() and not family.committed for family in selected)
    assert {family.name for family in selected} == {
        family.name for family in FAMILIES if family.producer is not None and not family.committed
    }
    # The Modelo wire types are committed source; a build seeding the window must never rewrite them.
    assert "modelo-wire-types" not in {family.name for family in selected}


_FIXTURE_IMPORT = re.compile(r"""@fixtures/([^/"'`]+)/""")
_FIXTURE_READ = re.compile(r"""windowFixture\(\s*"([^"]+)\"""")
_FRONTEND_TREES = ("src", "dev", "tests", ".storybook")


def test_every_projection_folder_the_frontend_reads_is_seeded_by_the_window_selection() -> None:
    produced = {output.split("/", 1)[0] for family in window_families() for output in family.outputs}
    read: set[str] = set()
    for tree in _FRONTEND_TREES:
        for path in (_FRONTEND / tree).rglob("*"):
            if path.suffix in {".ts", ".tsx", ".mts"} and "node_modules" not in path.parts:
                text = path.read_text(encoding="utf-8")
                read |= set(_FIXTURE_IMPORT.findall(text)) | set(_FIXTURE_READ.findall(text))
                if "MODELO_FIXTURES" in text:
                    read.add("modelo")
    assert read
    assert read <= produced, sorted(read - produced)


def test_the_frontend_type_check_is_the_host_preset_driver_and_never_a_bare_tsc() -> None:
    scripts = json.loads((_FRONTEND / "package.json").read_text(encoding="utf-8"))["scripts"]
    for name in ("build", "check"):
        assert scripts[name].startswith("node scripts/typecheck.mjs && "), name
        assert "tsc " not in scripts[name], name
    assert "scripts/tests/*.test.mjs" in scripts["check"]


def test_every_cmake_target_that_type_checks_the_frontend_seeds_the_window_projections_first() -> None:
    source = (REPO_ROOT / "native" / "desktop" / "CMakeLists.txt").read_text(encoding="utf-8")
    assert re.search(
        r"add_custom_target\(desktop-window-fixtures\s+COMMAND[^)]*dev\.fixture_projections seed --window", source
    )
    wired = re.search(
        r"foreach\(action IN ITEMS ([a-z ]+)\)\s*"
        r"add_dependencies\(desktop-frontend-\$\{action\}[^)]*\bdesktop-window-fixtures\b",
        source,
    )
    assert wired is not None
    assert set(wired.group(1).split()) == {"build", "check", "test"}
