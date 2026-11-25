"""Isolated detector tests for the real ty ``--fix`` mutation boundary."""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from dev.exit_codes import OK
from dev.paths import REPO_ROOT
from dev.quality import fixes

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]


def _isolated_tree() -> tempfile.TemporaryDirectory[str]:
    """Create ignored, disposable files inside the validated worktree scope."""
    scratch = REPO_ROOT / "var"
    scratch.mkdir(exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="ty-fix-detector-", dir=scratch)


def test_ty_fix_mutates_only_the_explicit_file_and_is_idempotent() -> None:
    """A known safe fix cannot spill into a neighboring Python file."""
    with _isolated_tree() as raw_root:
        root = Path(raw_root)
        target = root / "target.py"
        neighbor = root / "neighbor.py"
        suppression = '"""Detector fixture."""\n\nvalue: int = 1  # ty: ignore[invalid-assignment]\n'
        target.write_text(suppression, encoding="utf-8")
        neighbor.write_text(suppression, encoding="utf-8")

        assert fixes.main([str(target)]) == OK
        repaired = target.read_text(encoding="utf-8")
        assert repaired == '"""Detector fixture."""\n\nvalue: int = 1\n'
        assert neighbor.read_text(encoding="utf-8") == suppression

        assert fixes.main([str(target)]) == OK
        assert target.read_text(encoding="utf-8") == repaired
        assert neighbor.read_text(encoding="utf-8") == suppression


def test_unfixable_ty_diagnostic_remains_visible_but_does_not_fail_repair(capfd: pytest.CaptureFixture[str]) -> None:
    """Residual type findings are advisory after every mutator completes."""
    with _isolated_tree() as raw_root:
        target = Path(raw_root) / "target.py"
        target.write_text('"""Detector fixture."""\n\nvalue: int = "wrong"\n', encoding="utf-8")

        assert fixes.main([str(target)]) == OK
        captured = capfd.readouterr()
        assert "invalid-assignment" in captured.out + captured.err
        assert '"wrong"' in target.read_text(encoding="utf-8")


def test_a_warm_repair_spawns_one_run_of_each_tool_on_the_explicit_file_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bound the immediate loop by the work it does, which a loaded host's clock cannot inflate.

    A warm repair of one file starts exactly the fixed tool sequence, once each, and
    names that file and nothing else; a second process or a widened scope is the
    regression the old wall-clock ceiling stood in for.
    """
    spawned: list[tuple[str, ...]] = []
    real_run = fixes.subprocess.run

    def recording_run(command: Sequence[str], **kwargs: Any) -> object:
        spawned.append(tuple(command))
        return real_run(command, **kwargs)

    with _isolated_tree() as raw_root:
        target = Path(raw_root) / "target.py"
        target.write_text('"""Detector fixture."""\n\nvalue: int = 1\n', encoding="utf-8")
        assert fixes.main([str(target)]) == OK  # warm tool and filesystem caches
        repaired = target.read_text(encoding="utf-8")

        monkeypatch.setattr(fixes.subprocess, "run", recording_run)
        assert fixes.main([str(target)]) == OK

        expected = [(*prefix, "--", str(target.resolve())) for _, prefix, _ in fixes.REPAIR_COMMANDS]
        assert [(*command[:-1], str(Path(command[-1]).resolve())) for command in spawned] == expected
        assert target.read_text(encoding="utf-8") == repaired
