"""Real rendered-recipe tests for human-gated release guidance."""

from __future__ import annotations

import subprocess

import pytest

from ..._paths import REPO_ROOT
from ...ci.lane_reachability import resolve_just_executable

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = REPO_ROOT
_DISTRIBUTIONS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)


def _render_recipe(recipe: str, *args: str) -> str:
    just = resolve_just_executable()
    result = subprocess.run(  # noqa: S603 - execute the resolved real just binary against repository recipes.
        [just, "--dry-run", recipe, *args],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return f"{result.stdout}\n{result.stderr}"


def _recipe_summary() -> set[str]:
    just = resolve_just_executable()
    result = subprocess.run(  # noqa: S603 - resolved real just binary.
        [just, "--summary"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


def test_release_apply_is_absent_from_the_justfile() -> None:
    """The retired local-apply recipe is gone in full, not merely deprecated.

    The release pull request is the sole authority for advancing a version now:
    a deleted local path cannot be mis-invoked instead of the automated bump.
    Read directly off the tracked file rather than
    `just --summary` (which lists recipe NAMES only and would not catch a
    stray reference inside another recipe's body).
    """
    justfile_text = (_REPO_ROOT / "justfile").read_text(encoding="utf-8")

    assert "release-apply" not in justfile_text

    recipes = _recipe_summary()
    assert "release-apply" not in recipes


def test_release_survives_as_the_read_only_dry_run_preview() -> None:
    """`just release` still runs, previews only, and points at nothing deleted."""
    recipes = _recipe_summary()
    assert "release" in recipes

    rendered = _render_recipe("release")

    assert "--dry-run" in rendered
    assert "release-apply" not in rendered
    # Preview-only: the recipe body must not contain a real (non---dry-run)
    # mutating git push, since nothing downstream of the preview may act.
    assert "git push" not in rendered


def test_release_rollback_names_every_yank_target_and_only_the_rollback_tag() -> None:
    """The rendered rollback guide covers all distributions and one named tag."""
    rendered = _render_recipe("release-rollback", "1.2.3")

    for distribution in _DISTRIBUTIONS:
        assert f"https://pypi.org/manage/project/{distribution}/release/1.2.3/" in rendered
    assert "git push origin main" in rendered
    assert "git push origin refs/tags/v1.2.3-rollback" in rendered
    assert "git push origin main --tags" not in rendered


def test_doctor_invokes_the_aeat_human_cli() -> None:
    """The rendered workstation doctor uses the sole human CLI executable."""
    rendered = _render_recipe("doctor")

    assert "aeat config check" in rendered
    assert "cadrumo config check" not in rendered


def test_packaging_smoke_builds_one_cohort_before_every_consumer() -> None:
    """A fresh aggregate cannot reach a smoke lane before cohort construction.

    The aggregate routes through the campaign driver (ci-speed redesign), so
    the build-once-before-lanes invariant now lives in the driver: its serial
    pipeline builds the cohort exactly once, and only then fans the lanes out
    over the worker pool. The rendered recipe pins the routing; the driver
    source pins the ordering; every portable lane consumes the shared cohort
    directory by construction (`takes_cohort`).
    """
    rendered = _render_recipe("packaging-smoke")
    assert "dev.packaging.campaign --profile portable" in rendered

    from ...packaging.campaign import _COHORT_DIR, _PROFILES, resolve_form

    assert _COHORT_DIR == "var/packaging-smoke-cohort/python"
    assert all(resolve_form(selector)[1].takes_cohort for selector in _PROFILES["portable"])

    driver_source = (_REPO_ROOT / "dev" / "packaging" / "campaign.py").read_text(encoding="utf-8")
    assert driver_source.count('"build-cohort"') == 1
    assert driver_source.index('"build-cohort"') < driver_source.index("ThreadPoolExecutor(")


def test_local_upload_authority_is_absent_from_just() -> None:
    """Diagnostic release recipes remain, but local PyPI upload verbs do not."""
    recipes = _recipe_summary()
    assert "publish" not in recipes
    assert "publish-data" not in recipes
    assert "release" in recipes
    assert "release-readiness" in recipes
