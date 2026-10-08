"""Target-specific lock material stays distinct and conflicts remain refused."""

from __future__ import annotations

import runpy
import tomllib
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_HOME = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def helpers() -> tuple[dict[str, Any], dict[str, Any]]:
    generator = runpy.run_path(str(_HOME / "generate.py"))
    assertions = runpy.run_path(str(_HOME / "tests" / "test_homebrew_generate.py"))
    return generator, assertions


def test_disjoint_platform_versions_emit_only_their_locked_material(
    helpers: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    generator, assertions = helpers
    resource = generator["Resource"]
    macos = resource("forked-dependency", "darwin-source", "a" * 64, frozenset({"macos-arm64"}))
    linux = resource("forked-dependency", "linux-source", "b" * 64, frozenset({"linux-arm64", "linux-x86_64"}))
    formula = generator["_resource_blocks"]((macos, linux))
    observe = assertions["_formula_resources_for_target"]
    assert observe(formula, "macos-arm64") == {"forked-dependency": ("darwin-source", "a" * 64)}
    for target in ("linux-arm64", "linux-x86_64"):
        assert observe(formula, target) == {"forked-dependency": ("linux-source", "b" * 64)}


@pytest.mark.parametrize("changed", ("url", "sha256"))
def test_incompatible_material_on_an_overlapping_target_is_refused(
    helpers: tuple[dict[str, Any], dict[str, Any]], changed: str
) -> None:
    generator, _ = helpers
    resource = generator["Resource"]
    first = resource("forked-dependency", "first-source", "a" * 64, frozenset({"linux-arm64", "linux-x86_64"}))
    second = resource(
        "forked-dependency",
        "second-source" if changed == "url" else "first-source",
        "b" * 64 if changed == "sha256" else "a" * 64,
        frozenset({"linux-arm64"}),
    )
    with pytest.raises(SystemExit, match=r"material overlaps.*linux-arm64"):
        generator["_resource_blocks"]((first, second))


def test_real_lock_fork_projects_each_target_and_refuses_swapped_material(
    helpers: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    generator, assertions = helpers
    resource = generator["Resource"]
    lock_path = _HOME.parents[1] / "uv.lock"
    locked = generator["_locked_resources"](lock_path)
    backends = tuple(
        resource(name, url, digest, frozenset({"macos-arm64", "linux-arm64", "linux-x86_64"}))
        for name, url, digest in generator["_EXTRA_BUILD_BACKEND"]
    )
    formula = generator["_resource_blocks"]((*locked, *backends))
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    for target in ("macos-arm64", "linux-arm64", "linux-x86_64"):
        assertions["_assert_target_resources_match_lock"](formula, target, lock)
    observe = assertions["_formula_resources_for_target"]
    macos_material = observe(formula, "macos-arm64")["pikepdf"]
    linux_material = observe(formula, "linux-arm64")["pikepdf"]
    assert macos_material != linux_material
    swapped = formula.replace(macos_material[0], linux_material[0]).replace(macos_material[1], linux_material[1])
    with pytest.raises(AssertionError, match="pikepdf"):
        assertions["_assert_target_resources_match_lock"](swapped, "macos-arm64", lock)


def test_target_observer_refuses_duplicate_active_resource_names(
    helpers: tuple[dict[str, Any], dict[str, Any]],
) -> None:
    generator, assertions = helpers
    resource = generator["Resource"]
    material = resource("forked-dependency", "darwin-source", "a" * 64, frozenset({"macos-arm64"}))
    formula = generator["_resource_blocks"]((material,))
    with pytest.raises(AssertionError, match="forked-dependency"):
        assertions["_formula_resources_for_target"](formula + "\n" + formula, "macos-arm64")
