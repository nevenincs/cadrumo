"""The security diff scan runs the reset in a scratch worktree, never in the caller's tree.

Semgrep 1.168.0 implements `--baseline-commit` with `git reset --hard`. These
tests never invoke real semgrep -- the underlying orchestration is what needs
proving, not semgrep's own scanning. A stand-in scanner script is injected
through `semgrep_argv`, so the tests need no network access and no semgrep
installation; they exercise the real `git worktree` machinery against an
isolated temporary repository built fresh by each test.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from ..security_diff_scan import SecurityDiffScanError, merge_base, run_diff_scan

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_GIT_USER_ARGS = ("-c", "user.name=Cadrumo diff-scan test", "-c", "user.email=diff-scan-test@invalid.example")


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )


def _commit(cwd: Path, message: str) -> str:
    _git(*_GIT_USER_ARGS, "commit", "--quiet", "-m", message, cwd=cwd)
    return _git("rev-parse", "HEAD", cwd=cwd).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A small repo: a `main` baseline, a `feature` HEAD, and a dirty tracked file.

    `feature` branches from `main` after the baseline commit, so
    `merge_base("main")` resolves to the baseline commit rather than to HEAD
    itself. The dirty, uncommitted modification on `tracked.txt` stands in for
    another session's in-flight work: the whole point of the fix is that
    nothing here ever gets reset.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git("init", "--quiet", "-b", "main", cwd=root)
    (root / "tracked.txt").write_text("baseline\n", encoding="utf-8")
    _git("add", "tracked.txt", cwd=root)
    _commit(root, "baseline")

    _git("checkout", "--quiet", "-b", "feature", cwd=root)
    (root / "tracked.txt").write_text("baseline\nfeature\n", encoding="utf-8")
    _git("add", "tracked.txt", cwd=root)
    _commit(root, "feature work")

    # Another session's uncommitted, in-flight edit. This must survive the scan
    # byte for byte.
    (root / "tracked.txt").write_text("baseline\nfeature\nDIRTY UNCOMMITTED WORK\n", encoding="utf-8")

    return root


def _write_fake_scanner(tmp_path: Path, receipt: Path) -> Path:
    """A stand-in for `semgrep`: records what it saw, then exits with `FAKE_SCAN_EXIT_CODE`."""
    script = tmp_path / "fake_semgrep.py"
    script.write_text(
        textwrap.dedent(
            """
            import json
            import os
            import sys
            from pathlib import Path

            receipt = Path(sys.argv[1])
            tracked = Path("tracked.txt")
            receipt.write_text(
                json.dumps(
                    {
                        "argv": sys.argv[2:],
                        "cwd": str(Path.cwd()),
                        "tracked_contents": tracked.read_text(encoding="utf-8") if tracked.exists() else None,
                    }
                ),
                encoding="utf-8",
            )
            sys.exit(int(os.environ.get("FAKE_SCAN_EXIT_CODE", "0")))
            """
        ),
        encoding="utf-8",
    )
    return script


def _worktree_paths(repo_root: Path) -> list[str]:
    listing = _git("worktree", "list", "--porcelain", cwd=repo_root).stdout
    return [line.removeprefix("worktree ") for line in listing.splitlines() if line.startswith("worktree ")]


@pytest.mark.parametrize("fake_exit_code", [0, 1])
def test_dirty_tree_survives_and_findings_are_reported(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_exit_code: int
) -> None:
    dirty_before = (repo / "tracked.txt").read_text(encoding="utf-8")
    assert "DIRTY UNCOMMITTED WORK" in dirty_before

    receipt = tmp_path / "receipt.json"
    fake_scanner = _write_fake_scanner(tmp_path, receipt)
    monkeypatch.setenv("FAKE_SCAN_EXIT_CODE", str(fake_exit_code))

    exit_code = run_diff_scan(
        "main",
        root=repo,
        semgrep_argv=(sys.executable, str(fake_scanner), str(receipt)),
    )

    # The scanner's own exit code -- a finding -- is propagated verbatim. Only
    # the wrapper's own git/worktree failures use a different code.
    assert exit_code == fake_exit_code

    # The dirty file in the CALLER's tree is untouched: no reset ever reached it.
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == dirty_before

    receipt_data = json.loads(receipt.read_text(encoding="utf-8"))

    # The scan ran against HEAD's committed content, not the uncommitted edit,
    # and not in the caller's own working tree.
    assert receipt_data["tracked_contents"] == "baseline\nfeature\n"
    assert Path(receipt_data["cwd"]).resolve() != repo.resolve()

    # The correct merge-base was threaded through as `--baseline-commit`.
    baseline_sha = merge_base("main", root=repo)
    assert receipt_data["argv"][-1] == baseline_sha
    assert "--baseline-commit" in receipt_data["argv"]

    # No scratch worktree is left registered against the caller's repo.
    assert len(_worktree_paths(repo)) == 1


def test_scratch_worktree_is_removed_even_when_the_scanner_crashes(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dirty_before = (repo / "tracked.txt").read_text(encoding="utf-8")
    receipt = tmp_path / "receipt.json"
    fake_scanner = _write_fake_scanner(tmp_path, receipt)
    monkeypatch.setenv("FAKE_SCAN_EXIT_CODE", "2")  # simulates a semgrep internal error

    exit_code = run_diff_scan(
        "main",
        root=repo,
        semgrep_argv=(sys.executable, str(fake_scanner), str(receipt)),
    )

    assert exit_code == 2
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == dirty_before
    assert len(_worktree_paths(repo)) == 1


def test_invalid_base_raises_without_ever_creating_a_worktree(repo: Path, tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    fake_scanner = _write_fake_scanner(tmp_path, receipt)

    with pytest.raises(SecurityDiffScanError):
        run_diff_scan(
            "refs/heads/does-not-exist",
            root=repo,
            semgrep_argv=(sys.executable, str(fake_scanner), str(receipt)),
        )

    assert not receipt.exists()
    assert len(_worktree_paths(repo)) == 1
