"""Isolated detector tests for the real ty ``--fix`` mutation boundary."""

from __future__ import annotations

import math
import tempfile
import time
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT
from dev.exit_codes import OK
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


@pytest.mark.perf
def test_complete_warm_repair_stays_inside_the_two_second_p95_budget() -> None:
    """Keep the immediate-loop eligibility ceiling executable and explicit."""
    with _isolated_tree() as raw_root:
        target = Path(raw_root) / "target.py"
        target.write_text('"""Detector fixture."""\n\nvalue: int = 1\n', encoding="utf-8")
        assert fixes.main([str(target)]) == OK  # warm tool and filesystem caches

        durations: list[float] = []
        for _ in range(8):
            started = time.perf_counter()
            assert fixes.main([str(target)]) == OK
            durations.append(time.perf_counter() - started)

        p95 = sorted(durations)[math.ceil(0.95 * len(durations)) - 1]
        print(f"warm explicit-path repair p95: {p95:.3f}s")
        assert p95 <= 2.0, f"warm explicit-path repair p95 was {p95:.3f}s"
