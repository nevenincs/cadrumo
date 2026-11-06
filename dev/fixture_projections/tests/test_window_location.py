"""The window projections belong to the selected CMake build tree, and every consumer finds them there."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath

import pytest

from ...packaging.runtime_wheelhouse_contract import target_platform
from ...paths import REPO_ROOT
from ..location import (
    BINARY_DIRECTORY_VARIABLE,
    WINDOW_FIXTURES_KEY,
    WINDOW_INDEX,
    WINDOW_INDEX_FORMAT,
    WINDOW_ROOT,
    WindowProjectionsUnavailableError,
    host_preset,
    output_directory,
    selected_build,
    window_member,
    window_projections,
)
from ..registry import FAMILIES, window_families

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FRONTEND = REPO_ROOT / "native" / "desktop" / "frontend"
_DESKTOP_CMAKE = REPO_ROOT / "native" / "desktop" / "CMakeLists.txt"
#: The manifest key the frontend reads the projections under: the registry key, lowercased by BuildPaths.cmake.
_MANIFEST_KEY = WINDOW_FIXTURES_KEY.lower()


def _configure_presets() -> list[dict[str, object]]:
    document = json.loads((REPO_ROOT / "CMakePresets.json").read_text(encoding="utf-8"))
    return [preset for preset in document["configurePresets"] if not preset.get("hidden")]


def _other_preset() -> str:
    names = [str(preset["name"]) for preset in _configure_presets()]
    return next(name for name in names if name != host_preset())


def test_the_build_path_registry_declares_the_window_projections_and_its_cleanup_owns_them() -> None:
    source = (REPO_ROOT / "native" / "cmake" / "BuildPaths.cmake").read_text(encoding="utf-8")
    assert re.search(rf"^\s+{WINDOW_FIXTURES_KEY} {window_member()}$", source, re.MULTILINE)
    assert f'"{_MANIFEST_KEY}"' in source


def test_a_named_build_of_another_preset_holds_the_projections_and_the_host_presets_never_does(
    tmp_path: Path,
) -> None:
    other = _other_preset()
    build = tmp_path / "build" / other
    environment = {BINARY_DIRECTORY_VARIABLE: str(build)}

    projections = window_projections(tmp_path, environment)

    assert projections == build.joinpath(*window_member().parts)
    assert projections.is_relative_to(build)
    assert not projections.is_relative_to(tmp_path / "build" / host_preset())


def test_without_a_named_build_the_projections_are_the_host_presets(tmp_path: Path) -> None:
    assert selected_build(tmp_path, {}) == tmp_path / "build" / host_preset()
    assert window_projections(tmp_path, {}) == (tmp_path / "build" / host_preset()).joinpath(*window_member().parts)


@pytest.mark.parametrize(
    "named",
    ["build/windows-x64", "{root}/elsewhere/windows-x64", "{root}/build/windows-x64/nested", "{root}/build/../build/x"],
)
def test_a_named_directory_that_is_not_build_preset_of_the_checkout_is_refused(tmp_path: Path, named: str) -> None:
    with pytest.raises(WindowProjectionsUnavailableError, match=BINARY_DIRECTORY_VARIABLE):
        window_projections(tmp_path, {BINARY_DIRECTORY_VARIABLE: named.format(root=tmp_path.as_posix())})


def test_the_host_preset_is_the_one_visible_preset_of_its_own_that_targets_this_host() -> None:
    preset = next(preset for preset in _configure_presets() if preset["name"] == host_preset())
    assert "inherits" not in preset
    variables = preset["cacheVariables"]
    assert isinstance(variables, dict)
    assert target_platform(str(variables["CADRUMO_TARGET"])).name == variables["CADRUMO_TARGET"]


def test_a_window_family_output_root_resolves_to_the_window_projections(tmp_path: Path) -> None:
    assert output_directory("out", tmp_path) == tmp_path / "out"
    assert output_directory(WINDOW_ROOT, REPO_ROOT) == window_projections(REPO_ROOT)


def test_the_editor_alias_names_every_configure_presets_projection_directory_and_nothing_else() -> None:
    """tsconfig.json cannot know the selected build; its list only serves tools that run outside one."""
    configuration = json.loads((_FRONTEND / "tsconfig.json").read_text(encoding="utf-8"))
    declared = configuration["compilerOptions"]["paths"]["@fixtures/*"]
    assert declared == [
        f"../../../build/{preset['name']}/{PurePosixPath(window_member())}/*" for preset in _configure_presets()
    ]


def test_no_host_to_preset_table_remains_outside_the_presets() -> None:
    root_cmake = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    assert "cadrumo_fixture_preset" not in root_cmake
    assert "CADRUMO_WINDOW_FIXTURES " not in root_cmake
    for owner in (REPO_ROOT / "native" / "application" / "CMakeLists.txt", _DESKTOP_CMAKE):
        source = owner.read_text(encoding="utf-8")
        assert "CADRUMO_WINDOW_FIXTURES=${CADRUMO_PATH_WINDOW_FIXTURES}" in source, owner
        assert "${CADRUMO_WINDOW_FIXTURES}" not in source, owner
    assert not (_FRONTEND / "scripts" / "fixture-paths.mjs").exists()


@pytest.mark.parametrize(
    "reader",
    [
        "native/desktop/frontend/scripts/fixture-alias.mjs",
        "native/desktop/frontend/vite.config.ts",
        "native/desktop/frontend/tests/support/windowFixtures.ts",
        "native/desktop/scripts/frontend-build.mjs",
    ],
)
def test_every_frontend_reader_takes_the_projections_from_the_selected_builds_manifest(reader: str) -> None:
    source = (REPO_ROOT / reader).read_text(encoding="utf-8")
    assert f'buildPath("{_MANIFEST_KEY}")' in source
    assert "fixture-paths" not in source


def test_the_index_the_seed_writes_is_the_one_the_type_check_and_cmake_read() -> None:
    alias = (_FRONTEND / "scripts" / "fixture-alias.mjs").read_text(encoding="utf-8")
    assert f'export const WINDOW_INDEX = "{WINDOW_INDEX}";' in alias
    assert f'const WINDOW_INDEX_FORMAT = "{WINDOW_INDEX_FORMAT}";' in alias
    cmake = _DESKTOP_CMAKE.read_text(encoding="utf-8")
    assert f'set(desktop_window_index "${{CADRUMO_PATH_WINDOW_FIXTURES}}/{WINDOW_INDEX}")' in cmake


def test_a_generated_window_family_writes_inside_the_projection_directory() -> None:
    generated = [family for family in FAMILIES if family.producer is not None and not family.committed]
    assert generated
    for family in generated:
        assert family.output_root == WINDOW_ROOT, family.name


def test_the_window_selection_is_every_generated_window_family_and_no_committed_one() -> None:
    selected = window_families()
    assert selected
    assert all(family.output_root == WINDOW_ROOT and not family.committed for family in selected)
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


def test_the_frontend_type_check_is_the_bound_alias_driver_and_never_a_bare_tsc() -> None:
    scripts = json.loads((_FRONTEND / "package.json").read_text(encoding="utf-8"))["scripts"]
    for name in ("build", "check"):
        assert scripts[name].startswith("node scripts/typecheck.mjs && "), name
        assert "tsc " not in scripts[name], name
    assert "scripts/tests/*.test.mjs" in scripts["check"]
    playwright = (_FRONTEND / "playwright.config.ts").read_text(encoding="utf-8")
    assert "writeAliasProject(" in playwright
    assert re.search(r"defineConfig\(\{[^}]*\btsconfig,", playwright)


def test_the_window_seed_is_an_incremental_step_whose_output_is_the_index() -> None:
    source = _DESKTOP_CMAKE.read_text(encoding="utf-8")
    command = re.search(r'add_custom_command\(OUTPUT "\$\{desktop_window_index\}"(.*?)VERBATIM\)', source, re.DOTALL)
    assert command is not None
    body = command.group(1)
    assert re.search(r"dev\.fixture_projections seed --window --depfile \"\$\{desktop_window_depfile\}\"", body)
    assert 'DEPFILE "${desktop_window_depfile}"' in body
    assert 'DEPENDS ${desktop_window_seeder} "${desktop_window_listing}"' in body
    assert re.search(r'add_custom_target\(desktop-window-fixtures DEPENDS "\$\{desktop_window_index\}"\)', source)


def test_an_input_file_added_beside_the_others_reruns_the_seed_through_the_listing_and_no_directory() -> None:
    source = _DESKTOP_CMAKE.read_text(encoding="utf-8")
    listing = re.search(r"add_custom_target\(desktop-window-inputs\s(.*?)VERBATIM\)", source, re.DOTALL)
    assert listing is not None
    body = listing.group(1)
    # A custom target runs on every build; its byproduct changes only when the listing does, so the seed reruns
    # only then, under the Visual Studio and the Ninja generators alike.
    assert re.search(r"dev\.fixture_projections window-listing \"\$\{desktop_window_listing\}\"", body)
    assert 'BYPRODUCTS "${desktop_window_listing}"' in body
    assert re.search(r"add_dependencies\(desktop-window-fixtures [^)]*\bdesktop-window-inputs\b", source)


def test_every_cmake_target_that_type_checks_the_frontend_seeds_the_window_projections_first() -> None:
    source = _DESKTOP_CMAKE.read_text(encoding="utf-8")
    wired = re.search(
        r"foreach\(action IN ITEMS ([a-z ]+)\)\s*"
        r"add_dependencies\(desktop-frontend-\$\{action\}[^)]*\bdesktop-window-fixtures\b",
        source,
    )
    assert wired is not None
    assert set(wired.group(1).split()) == {"build", "check", "test"}
