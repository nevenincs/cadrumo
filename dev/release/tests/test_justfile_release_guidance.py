"""Real rendered-recipe tests for human-gated release guidance."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DISTRIBUTIONS = (
    "cadrumo",
    "cadrumo-data-manuals",
    "cadrumo-data-official",
)


def _render_recipe(recipe: str, *args: str) -> str:
    just = shutil.which("just")
    assert just is not None, "just is required to validate release recipes"
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
    just = shutil.which("just")
    assert just is not None
    result = subprocess.run(  # noqa: S603 - resolved real just binary.
        [just, "--summary"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


def test_release_apply_names_every_version_authority_and_only_the_named_tag() -> None:
    """The rendered apply guide covers the cohort, lock, and explicit final tag."""
    rendered = _render_recipe("release-apply")

    assert "packaging/cadrumo_data_manuals/pyproject.toml" in rendered
    assert "packaging/cadrumo_data_official/pyproject.toml" in rendered
    # The .mcpb manifest is NOT a bumped surface. Its tracked "version" is a
    # synthetic sentinel that `check_version_surfaces_agree` requires to stay
    # put (`dev/release/readiness.py`), because a real-looking literal there
    # would masquerade as an authority; `packaging/mcpb/build.py` stamps the
    # real cohort version over it at build time. Instructing a bump there fails
    # the blocking version gate, so the checklist names SEVEN authorities and
    # must not stage the manifest.
    #
    # Asserted on the instruction and the staged set, not on the bare path:
    # the checklist mentions the manifest precisely to say "do not touch it",
    # so a substring check for the path alone would pass either way.
    assert "seven release authorities" in rendered
    assert "Update packaging/mcpb/manifest.json" not in rendered
    assert "src/cadrumo/__init__.py CHANGELOG.md uv.lock" in rendered
    assert "mandatory base dependency pins" in rendered
    assert "cadrumo-data-manuals==X.Y.Z" in rendered
    assert "cadrumo-data-official==X.Y.Z" in rendered
    assert "corpus-sources" not in rendered
    assert "uv lock" in rendered
    assert "uv lock --check" in rendered
    assert "just release-readiness" in rendered
    assert "git push origin main" in rendered
    assert "git push origin refs/tags/vX.Y.Z" in rendered
    assert "git push origin main --tags" not in rendered


def test_release_collect_evidence_aggregates_rows_from_evidence_drafts() -> None:
    """The collect recipe downloads every row from the runs' evidence drafts.

    Release-asset transport: rows ride draft releases tagged
    evidence-<lane>-<run_id>, never Actions artifacts, and the sealed
    evidence-manifest.json asset is not a row.
    """
    rendered = _render_recipe("release-collect-evidence", "123456")

    assert "gh run download" not in rendered
    assert "gh release download" in rendered
    assert "evidence-$lane-" in rendered or "evidence-$lane-$run_id" in rendered
    assert "evidence-manifest.json" in rendered
    assert "var/distribution-install-readiness" in rendered


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

    from dev.packaging.campaign import _COHORT_DIR, _LANES, _PROFILES

    assert _COHORT_DIR == "var/packaging-smoke-cohort/python"
    assert all(_LANES[name].takes_cohort for name in _PROFILES["portable"])

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
