"""The first-party source classification, on planted paths and on the live tree."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from dev._paths import REPO_ROOT
from dev.first_party_source import (
    FIRST_PARTY_ROOTS,
    PRODUCT_PACKAGE,
    is_bundled_data,
    is_production_source,
    is_test_module_name,
    is_test_source,
    production_exclusion_globs,
)
from dev.source_tree import repository_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRODUCTION = (
    "src/cadrumo/domain/rates.py",
    "src/cadrumo/__init__.py",
    "dev/test_runs/command.py",
    "packaging/authority/hatch_build.py",
)
_TEST = (
    "src/cadrumo/domain/tests/test_rates.py",
    "src/cadrumo/domain/tests/support.py",
    "src/cadrumo/domain/tests/__init__.py",
    "src/cadrumo/domain/test_rates.py",
    "src/cadrumo/domain/_test_support.py",
    "src/cadrumo/conftest.py",
    "dev/registry/conftest.py",
)
_DATA = ("src/cadrumo/_data/__init__.py", "src/cadrumo/_data/corpus/__init__.py")


@pytest.mark.parametrize("path", _PRODUCTION)
def test_production_modules_are_production(path: str) -> None:
    assert is_production_source(path)
    assert not is_test_source(path)


@pytest.mark.parametrize("path", _TEST)
def test_the_test_surface_is_never_production(path: str) -> None:
    assert is_test_source(path)
    assert not is_production_source(path)


@pytest.mark.parametrize("path", _DATA)
def test_bundled_data_is_never_production(path: str) -> None:
    assert is_bundled_data(path)
    assert not is_test_source(path)
    assert not is_production_source(path)


def test_a_non_python_file_is_not_production_source() -> None:
    assert not is_production_source("src/cadrumo/locales/es.yaml")


def test_an_absolute_path_is_refused_unless_its_root_is_given(tmp_path: Path) -> None:
    """A checkout under a directory named ``tests`` must not read as all test code."""
    checkout = tmp_path / "tests" / "clone"
    module = checkout / "src" / "cadrumo" / "rates.py"

    with pytest.raises(ValueError, match="relative path"):
        is_test_source(module)
    assert is_production_source(module, root=checkout)
    assert is_test_source(checkout / "src" / "cadrumo" / "tests" / "x.py", root=checkout)


def test_module_names_follow_the_same_convention() -> None:
    assert is_test_module_name("cadrumo.domain.tests")
    assert is_test_module_name("cadrumo.domain.tests.support")
    assert is_test_module_name("cadrumo.conftest")
    assert is_test_module_name("cadrumo.domain.test_rates")
    assert not is_test_module_name("cadrumo.domain.rates")


def test_the_exclusion_globs_reject_exactly_what_the_predicate_rejects() -> None:
    """Tools fed the globs must measure the population the predicate admits.

    Checked on the live product tree, so a convention added to the predicate
    and not to the globs (or the reverse) is caught where it matters.
    """
    globs = production_exclusion_globs()
    python_files = [path for path in repository_files(REPO_ROOT, under=(PRODUCT_PACKAGE,)) if path.endswith(".py")]

    disagreements = [
        path
        for path in python_files
        if is_production_source(path) == any(PurePosixPath(path).full_match(glob) for glob in globs)
    ]

    assert len(python_files) > 3000, f"only {len(python_files)} product modules were enumerated"
    assert any(not is_production_source(path) for path in python_files)
    assert disagreements == []


def test_every_first_party_root_exists() -> None:
    missing = [root for root in FIRST_PARTY_ROOTS if not (REPO_ROOT / root).is_dir()]
    assert missing == []
