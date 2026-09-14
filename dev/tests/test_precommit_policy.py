"""Pins the repository's uninstalled-hook and explicit-repair boundary."""

from __future__ import annotations

import pytest

from dev._paths import REPO_ROOT
from dev.init import plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_setup_has_no_git_hook_installer_or_git_configuration_mutation() -> None:
    """Neither setup data nor the historical module can install a commit hook."""
    commands = tuple(step.argv for phase in plan.PHASE_PLAN.values() for step in phase.steps)
    flattened = "\n".join(" ".join(command) for command in commands).lower()
    assert "prek install" not in flattened
    assert "pre-commit install" not in flattened
    assert "git config" not in flattened
    assert not (REPO_ROOT / "dev" / "init" / "hooks.py").exists()


def test_fix_code_requires_and_quotes_one_caller_owned_path() -> None:
    """The Just facade cannot silently become a whole-tree repair."""
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    assert "fix-code PATH:" in justfile
    assert "python -m dev.quality.fixes {{quote(PATH)}}" in justfile
    assert "fix-code:\n" not in justfile


def test_prek_replay_uses_locked_local_ruff_and_never_repairs() -> None:
    """Manual replay has no second Ruff version or mutating command."""
    config = (REPO_ROOT / "prek.toml").read_text(encoding="utf-8")
    assert "astral-sh/ruff-pre-commit" not in config
    assert 'entry = "uv run --no-sync ruff check"' in config
    assert 'entry = "uv run --no-sync ruff format --check"' in config
    assert "ruff check --fix" not in config
    assert "ty check --fix" not in config
