"""Pins the repository's uninstalled-hook and explicit-repair boundary."""

from __future__ import annotations

import pytest

from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _recipe_body(justfile: str, name: str) -> str:
    """Return the indented command lines of one justfile recipe, lowercased."""
    lines = justfile.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith((f"{name}:", f"{name} ")))
    body: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith((" ", "\t")):
            break
        body.append(line.strip())
    return "\n".join(body).lower()


def test_setup_has_no_git_hook_installer_or_git_configuration_mutation() -> None:
    """Neither worktree setup recipe can install a commit hook or change Git configuration."""
    justfile = (REPO_ROOT / "justfile").read_text(encoding="utf-8")
    setup = _recipe_body(justfile, "setup")
    commands = f"{setup}\n{_recipe_body(justfile, 'init')}"
    assert "python -m dev.init all" in setup
    initializer = (REPO_ROOT / "dev/init/plan.py").read_text(encoding="utf-8")
    assert '"sync"' in initializer
    assert "prek install" not in commands
    assert "pre-commit install" not in commands
    assert "git config" not in commands


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
