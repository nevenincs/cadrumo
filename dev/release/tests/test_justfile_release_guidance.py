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


def test_release_apply_names_every_version_authority_and_only_the_named_tag() -> None:
    """The rendered apply guide covers the cohort, lock, and explicit final tag."""
    rendered = _render_recipe("release-apply")

    assert "packaging/cadrumo_data_manuals/pyproject.toml" in rendered
    assert "packaging/cadrumo_data_official/pyproject.toml" in rendered
    assert "cadrumo-data-manuals==X.Y.Z" in rendered
    assert "cadrumo-data-official==X.Y.Z" in rendered
    assert "uv lock" in rendered
    assert "uv lock --check" in rendered
    assert "just release-readiness" in rendered
    assert "git push origin main" in rendered
    assert "git push origin refs/tags/vX.Y.Z" in rendered
    assert "git push origin main --tags" not in rendered


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
