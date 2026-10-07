"""The dead-code gate that runs a real vulture scan over the tree.

Spawns the real ``uv run --no-sync vulture`` invocation and reads what it
actually reports, so this is ``integration``: it needs the real dev
dependency installed and walks the whole production tree. The parsing and
classification checks are in ``test_dead_code``; this module only proves the
runner against a live process.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.packaging.command_execution import run_command

from ..dead_code import (
    MINIMUM_OFFERED_MODULES,
    DeadCodeOutcome,
    offered_module_population,
    parse_vulture_output,
    run_dead_code_scan,
    vulture_command,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def _isolated_vulture_config(tmp_path: Path) -> Path:
    """Write a config that leaves an explicitly supplied candidate in scope."""
    config = tmp_path / "vulture.toml"
    config.write_text("[tool.vulture]\nmin_confidence = 60\n", encoding="utf-8")
    return config


def _expected_vulture_path(path: Path) -> str:
    """Render *path* the way vulture's own ``format_path`` reports it.

    ``vulture.utils.format_path`` renders a path relative to the process's
    current working directory (the repo root here, via ``cwd=_REPO_ROOT``)
    when it resolves under it, and falls back to the path exactly as given
    otherwise. The run harness confines pytest's basetemp under the
    repository's own ``.logs`` tree, so ``tmp_path`` candidates land inside
    the repo root and vulture reports them relative -- with the OS-native
    separator, not the POSIX form the repo-relative helpers elsewhere use.
    Mirroring the real contract keeps the assertion about vulture's actual
    rendering rule rather than assuming a particular basetemp location.
    """
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


def test_real_scan_over_the_tree_returns_a_typed_outcome_with_real_findings() -> None:
    """A real vulture run classifies to CLEAN or FINDINGS, never a crash.

    No self-skip on a clean tree (forbidden by ``test_no_skip_xfail`` for
    tests outside the source tree, per the sibling ``test_duplication_scan``'s
    own convention): both branches are asserted inside one test instead.
    """
    result = run_dead_code_scan(_REPO_ROOT)

    assert result.outcome in {DeadCodeOutcome.CLEAN, DeadCodeOutcome.FINDINGS}
    assert result.headline()

    if result.outcome is DeadCodeOutcome.FINDINGS:
        for finding in result.findings:
            assert (_REPO_ROOT / finding.path).is_file(), f"vulture named a path that does not exist: {finding.path}"
            assert finding.line > 0
            assert 0 <= finding.confidence <= 100


@pytest.mark.parametrize("unused_name", ("quota_project_id", "clock_skew_in_seconds", "interaction_facts"))
def test_whitelist_does_not_mask_former_protocol_parameter_names(tmp_path: Path, unused_name: str) -> None:
    """The live whitelist leaves unrelated unused names detectable by vulture."""
    candidate = tmp_path / "candidate.py"
    candidate.write_text(f"def {unused_name}():\n    pass\n", encoding="utf-8")
    config = _isolated_vulture_config(tmp_path)

    completed = run_command(
        [
            "uv",
            "run",
            "--no-sync",
            "vulture",
            "--config",
            str(config),
            str(candidate),
            "dev/audit/vulture_whitelist.py",
        ],
        cwd=_REPO_ROOT,
    )

    assert completed.returncode == 3, completed.stderr
    assert f"{_expected_vulture_path(candidate)}:" in completed.stdout
    assert f"unused function '{unused_name}'" in completed.stdout


def test_vulture_detects_a_type_import_used_only_in_a_quoted_cast(tmp_path: Path) -> None:
    """A quoted cast does not make a runtime type import live to Vulture."""
    candidate = tmp_path / "candidate.py"
    candidate.write_text(
        'from sqlalchemy import Table as _Table\nfrom typing import cast\n\ncast("_Table", object())\n',
        encoding="utf-8",
    )
    config = _isolated_vulture_config(tmp_path)

    completed = run_command(
        [
            "uv",
            "run",
            "--no-sync",
            "vulture",
            "--config",
            str(config),
            str(candidate),
        ],
        cwd=_REPO_ROOT,
    )

    assert completed.returncode == 3, completed.stderr
    assert f"{_expected_vulture_path(candidate)}:" in completed.stdout
    assert "unused import '_Table'" in completed.stdout


def test_a_repo_root_offering_no_module_refuses_before_launching_vulture(tmp_path: Path) -> None:
    """An empty target set must not read as a clean tree.

    Vulture exits 0 both for a tree it read and found clean and for targets
    that offer it nothing, and that exit code was mapped straight to CLEAN.

    The ordering is proved rather than assumed: a launched subprocess under
    ``timeout=0.0`` would come back as the timeout reason. Getting the
    offered-population reason instead is what shows the refusal is taken
    first, so this case costs no vulture run.
    """
    result = run_dead_code_scan(tmp_path, timeout=0.0)

    assert result.outcome is DeadCodeOutcome.ERROR
    assert result.is_green is False
    assert "would prove nothing about dead code" in result.reason
    assert "0 Python module(s)" in result.reason


def test_an_emptied_production_tree_refuses_though_one_target_file_survives(tmp_path: Path) -> None:
    """The floor exists because a bare ``> 0`` could not see this shape.

    ``_TARGETS`` names the production package and one whitelist file. If the
    package is emptied but the whitelist survives, the offered population is
    1, not 0 -- vulture is handed real paths, analyses nothing of substance,
    and exits 0. An existence check would pass and the scan would read clean.
    """
    (tmp_path / "src" / "cadrumo").mkdir(parents=True)
    whitelist = tmp_path / "dev" / "audit"
    whitelist.mkdir(parents=True)
    (whitelist / "vulture_whitelist.py").write_text("", encoding="utf-8")

    assert offered_module_population(tmp_path) == 1

    result = run_dead_code_scan(tmp_path, timeout=0.0)

    assert result.outcome is DeadCodeOutcome.ERROR
    assert result.is_green is False
    assert "1 Python module(s)" in result.reason
    assert "timeout" not in result.reason


def test_a_config_excluding_the_product_refuses_before_launch(tmp_path: Path) -> None:
    """A broad exclusion makes the offered population empty even with real source present."""
    _populated_tree(tmp_path)
    (tmp_path / "pyproject.toml").write_text('[tool.vulture]\nexclude = ["*cadrumo*"]\n', encoding="utf-8")

    result = run_dead_code_scan(tmp_path, timeout=0.0)

    assert result.outcome is DeadCodeOutcome.ERROR
    assert "0 Python module(s)" in result.reason
    assert "timeout" not in result.reason


def test_invalid_vulture_configuration_is_unavailable(tmp_path: Path) -> None:
    """Invalid options must produce an unavailable result instead of crashing the audit."""
    (tmp_path / "pyproject.toml").write_text("[tool.vulture]\nunknown_option = true\n", encoding="utf-8")

    result = run_dead_code_scan(tmp_path)

    assert result.outcome is DeadCodeOutcome.ERROR
    assert "configuration could not be read" in result.reason


def test_product_exclusions_match_a_real_vulture_scan(tmp_path: Path) -> None:
    """Real Vulture selects product source even below pytest's test-named directory."""
    (tmp_path / "pyproject.toml").write_bytes((_REPO_ROOT / "pyproject.toml").read_bytes())
    for relative in (
        "src/cadrumo/domain/one.py",
        "src/cadrumo/domain/test_one.py",
        "src/cadrumo/domain/_test_two.py",
        "src/cadrumo/domain/tests/helper.py",
        "src/cadrumo/domain/_data/content.py",
        "src/cadrumo/domain/conftest.py",
        "native/desktop/src-tauri/src/python/cli.py",
        "dev/packaging/native/build.py",
        "build/runtime/copied.py",
    ):
        module = tmp_path / relative
        module.parent.mkdir(parents=True, exist_ok=True)
        module.write_text("import math\n", encoding="utf-8")
    whitelist = tmp_path / "dev/audit/vulture_whitelist.py"
    whitelist.parent.mkdir(parents=True, exist_ok=True)
    whitelist.write_text("", encoding="utf-8")

    completed = run_command(
        [
            "uv",
            "run",
            "--project",
            str(_REPO_ROOT),
            "--no-sync",
            "vulture",
            "--config",
            str(tmp_path / "pyproject.toml"),
            str(tmp_path / "src/cadrumo"),
            str(whitelist),
        ],
        cwd=_REPO_ROOT,
    )

    assert completed.returncode == 3, completed.stderr
    findings = parse_vulture_output(completed.stdout)
    assert [(finding.path, finding.message) for finding in findings] == [
        (_expected_vulture_path(tmp_path / "src/cadrumo/domain/one.py").replace("\\", "/"), "unused import 'math'"),
    ]
    assert offered_module_population(tmp_path) == 2


def _populated_tree(root: Path) -> Path:
    """Build a tree that clears the population floor and holds one dead import."""
    package = root / "src" / "cadrumo"
    package.mkdir(parents=True)
    for index in range(MINIMUM_OFFERED_MODULES):
        (package / f"module_{index:05d}.py").write_text("", encoding="utf-8")
    (package / "dead.py").write_text("import os\n", encoding="utf-8")
    whitelist = root / "dev" / "audit"
    whitelist.mkdir(parents=True)
    (whitelist / "vulture_whitelist.py").write_text("", encoding="utf-8")
    # No pyproject.toml: vulture falls back to its defaults when the configured
    # file is absent, and a manifest here would make ``uv run`` adopt this
    # directory as a project instead of the synced environment.
    return package


def test_a_module_vulture_cannot_parse_makes_the_scan_unavailable(tmp_path: Path) -> None:
    """A skipped module must not let the remaining findings pose as the whole list.

    vulture reports an unparseable module on stderr, leaves it out, and still
    exits 3 when the other modules hold findings. The same tree is scanned
    before and after the one unparseable module is added, so the change in
    outcome is attributable to that module alone.
    """
    package = _populated_tree(tmp_path)

    complete = run_dead_code_scan(tmp_path)

    assert complete.outcome is DeadCodeOutcome.FINDINGS, complete.reason
    assert [(finding.path, finding.message) for finding in complete.findings] == [
        ("src/cadrumo/dead.py", "unused import 'os'"),
    ]

    (package / "broken.py").write_text("x = 1_\n", encoding="utf-8")

    raw = run_command(vulture_command(), errors="replace", cwd=tmp_path)
    assert raw.returncode == 3, raw.stderr
    assert "dead.py:1: unused import 'os'" in raw.stdout

    partial = run_dead_code_scan(tmp_path)

    assert partial.outcome is DeadCodeOutcome.ERROR
    assert partial.is_green is False
    assert partial.findings == ()
    assert "skipped 1 module(s)" in partial.reason
    assert "src/cadrumo/broken.py (invalid decimal literal" in partial.reason
