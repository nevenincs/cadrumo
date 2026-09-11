"""Behavioral tests for the shared source and test inventory helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.tests.inventory import (
    FIXTURES_DIR,
    REPO_ROOT,
    SRC_CADRUMO,
    aeat_relative,
    ast_for_path,
    discover_test_control_modules,
    discover_test_modules,
    module_name,
    non_test_package_python_files,
    non_test_python_files_under,
    package_python_files,
    production_python_files,
    repo_path,
    repo_relative,
)

from ._project_inventory import project_test_control_modules, project_test_modules

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_source_test_inventory_discovers_tests_without_fixture_payloads() -> None:
    modules = discover_test_modules()
    assert repo_path("src/cadrumo/tests/test_wheel_content_boundary.py") in modules
    assert all(not path.is_relative_to(FIXTURES_DIR) for path in modules)


def test_test_control_inventory_includes_support_and_conftest_modules() -> None:
    modules = discover_test_control_modules()
    assert repo_path("src/cadrumo/tests/inventory.py") in modules
    assert repo_path("src/cadrumo/application/conftest.py") in modules
    assert all(not path.is_relative_to(FIXTURES_DIR) for path in modules)


def test_repository_path_rendering_round_trips() -> None:
    current = Path(__file__).resolve()
    relative = repo_relative(current)
    assert relative == "dev/tests/test_test_inventory.py"
    assert repo_path(relative) == current
    assert repo_path(relative).is_relative_to(REPO_ROOT)


def test_package_relative_path_rendering_is_posix() -> None:
    package_test = repo_path("src/cadrumo/tests/test_wheel_content_boundary.py")
    assert aeat_relative(package_test) == "tests/test_wheel_content_boundary.py"


def test_production_inventory_excludes_test_control_and_data_modules() -> None:
    files = production_python_files()
    package_root = repo_path("src/cadrumo")
    assert repo_path("src/cadrumo/core/config.py") in files
    assert repo_path("src/cadrumo/conftest.py") not in files
    assert all("tests" not in path.relative_to(package_root).parts for path in files)
    assert all("_data" not in path.relative_to(package_root).parts for path in files)


def test_package_inventory_includes_tests_and_excludes_data_by_default() -> None:
    files = package_python_files()
    assert repo_path("src/cadrumo/core/config.py") in files
    assert repo_path("src/cadrumo/tests/test_wheel_content_boundary.py") in files
    assert all("_data" not in path.relative_to(SRC_CADRUMO).parts for path in files)


def test_project_inventory_discovers_tests_outside_the_source_tree() -> None:
    modules = project_test_modules()
    controls = project_test_control_modules()
    assert Path(__file__).resolve() in modules
    assert Path(__file__).resolve() in controls
    assert repo_path("dev/tests/_project_inventory.py") in controls
    assert repo_path("dev/tests/_project_inventory.py") not in modules


def test_non_test_package_inventory_excludes_test_modules() -> None:
    files = non_test_package_python_files()
    assert repo_path("src/cadrumo/core/config.py") in files
    assert repo_path("src/cadrumo/tests/test_wheel_content_boundary.py") not in files


def test_non_test_inventory_accepts_a_package_or_direct_module() -> None:
    package_files = non_test_python_files_under(repo_path("src/cadrumo/core"))
    direct_file = repo_path("src/cadrumo/core/config.py")
    assert direct_file in package_files
    assert tuple(non_test_python_files_under(direct_file)) == (direct_file,)


def test_real_module_ast_and_import_name_resolve() -> None:
    path = repo_path("src/cadrumo/core/config.py")
    assert ast_for_path(path) is not None
    assert module_name(path) == "cadrumo.core.config"
