"""Prove the checkout-drift screen measures the class it claims and refuses an empty one.

Every case drives the real :func:`measure` over a real git repository created
in a temporary directory: a genuine ``git init``, a genuine commit, and genuine
working-tree bytes. Nothing here is patched, and no fixture stands in for git,
because the entire claim under test is about the difference between what git
reports and what is actually on disk. A test double for git would be a double
of the exact component whose blindness is the subject.

The reference measurement this screen was built against, taken over the real
repository, was 1137 tracked files whose on-disk bytes differed from their
committed bytes while ``git diff`` reported every one of them clean, all 1137
carrying CRLF. The first case below is that situation reduced to one file, with
git's silence asserted rather than assumed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ..._paths import UTF_8 as _UTF_8
from ..checkout_drift import (
    blob_hash,
    growth_against_ceiling,
    load_ceiling,
    measure,
    write_ceiling,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: Applied to every temporary repository so the checkout semantics match the
#: real one: git stores and checks out LF regardless of platform, which is what
#: makes a CRLF working copy evidence of a post-checkout rewrite.
_ATTRIBUTES = b"* text=auto eol=lf\n"


def _git(root: Path, *args: str) -> str:
    """Run git in *root*, failing loudly with its stderr.

    ``core.autocrlf`` is pinned off so the temporary repositories behave the
    same on a machine whose global git config sets it; otherwise the fixture's
    checkout semantics would depend on the contributor's environment and the
    cases would pass or fail for reasons unrelated to the code.
    """
    executable = shutil.which("git")
    assert executable is not None, "git must be on PATH for these cases to mean anything"
    result = subprocess.run(
        [executable, "-c", "core.autocrlf=false", *args],
        cwd=root,
        capture_output=True,
        text=True,
        encoding=_UTF_8,
        check=False,
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result.stdout


def _repo_with_committed_files(root: Path, files: dict[str, bytes]) -> None:
    """Create a git repository at *root* holding *files*, committed with LF."""
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q", "-b", "main")
    (root / ".gitattributes").write_bytes(_ATTRIBUTES)
    for name, payload in files.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    _git(root, "add", "-A")
    _git(
        root,
        "-c",
        "user.email=screen@example.invalid",
        "-c",
        "user.name=screen",
        "commit",
        "-q",
        "-m",
        "seed",
    )


def test_measure_finds_a_file_rewritten_after_checkout(tmp_path: Path) -> None:
    """A file whose terminators were translated on disk is reported, and git is silent about it.

    The middle assertion is the load-bearing one. If git reported the file as
    modified, the screen would be measuring something git already surfaces and
    would be redundant; the whole reason this class needs an instrument is that
    the normalisation makes the difference invisible from the git side.
    """
    root = tmp_path / "repo"
    _repo_with_committed_files(root, {"module.py": b"alpha\nbeta\ngamma\n"})

    target = root / "module.py"
    target.write_bytes(b"alpha\r\nbeta\r\ngamma\r\n")

    assert _git(root, "diff", "--name-only", "HEAD").strip() == "", (
        "git must report the translated file as clean, or this class is not silent and needs no screen"
    )

    measurement = measure(root)

    assert measurement.drifted == ("module.py",)
    assert measurement.carrying_crlf == 1
    assert measurement.buckets == {"module.py": 1}
    assert measurement.scanned >= 2, "the screen must have hashed the seeded files, not zero of them"


def test_measure_excludes_a_file_carrying_ordinary_uncommitted_edits(tmp_path: Path) -> None:
    """A genuinely edited file is not a finding, and a translated sibling still is.

    Both files differ from their committed blob. Only one of them differs
    silently. Reporting both would bury the silent class under every
    contributor's live work, which in a shared worktree is most of the tree.
    """
    root = tmp_path / "repo"
    _repo_with_committed_files(
        root,
        {"edited.py": b"one\ntwo\n", "translated.py": b"one\ntwo\n"},
    )

    (root / "edited.py").write_bytes(b"one\ntwo\nthree\n")
    (root / "translated.py").write_bytes(b"one\r\ntwo\r\n")

    assert _git(root, "diff", "--name-only", "HEAD").split() == ["edited.py"], (
        "git must see exactly the real edit and not the translation, or the exclusion proves nothing"
    )

    measurement = measure(root)

    assert measurement.drifted == ("translated.py",)


def test_measure_refuses_a_repository_with_no_tracked_files(tmp_path: Path) -> None:
    """An empty tree refuses instead of reporting a clean zero.

    A screen that scanned nothing produces the same total as a healthy tree, so
    the clean result is only evidence when the scan demonstrably happened.
    """
    root = tmp_path / "empty"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(
        root,
        "-c",
        "user.email=screen@example.invalid",
        "-c",
        "user.name=screen",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "empty",
    )

    with pytest.raises(SystemExit, match="no tracked files"):
        measure(root)


def test_measure_refuses_when_every_tracked_file_is_excluded(tmp_path: Path) -> None:
    """Tracked files that are all skipped is a vacuous scan, not a clean one.

    This is the subtler half of the vacuity floor. The tree is not empty, so
    the first refusal does not fire; the walk still hashes nothing, and a total
    of zero would read as a healthy repository.
    """
    root = tmp_path / "repo"
    _repo_with_committed_files(root, {"only.py": b"one\n"})

    (root / ".gitattributes").unlink()
    (root / "only.py").unlink()

    with pytest.raises(SystemExit, match="hashed zero files"):
        measure(root)


def test_blob_hash_agrees_with_git_on_real_bytes(tmp_path: Path) -> None:
    """The locally computed object name matches git's, including for CRLF payloads.

    The screen reimplements git's object naming so the measurement can bypass
    the input filters that hide this class. That reimplementation is the single
    point where the whole instrument could be systematically wrong while every
    other assertion still passed, so it is checked against git itself rather
    than against a remembered algorithm.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")

    payloads = {
        "lf.txt": b"alpha\nbeta\n",
        "crlf.txt": b"alpha\r\nbeta\r\n",
        "empty.txt": b"",
        "binary.bin": bytes(range(256)),
        "utf8.txt": "declaración\ncasilla\n".encode(_UTF_8),
    }
    for name, payload in payloads.items():
        (root / name).write_bytes(payload)
        expected = _git(root, "hash-object", "--no-filters", name).strip()
        assert blob_hash(payload) == expected, f"object name disagrees with git for {name}"


def test_growth_against_ceiling_treats_an_unrecorded_tree_as_growth(tmp_path: Path) -> None:
    """A drifted tree absent from the ceiling is growth, not an unmeasured free pass.

    Defaulting a missing bucket to "no ceiling" would let an entire new tree
    drift without moving the recorded total enough to notice.
    """
    root = tmp_path / "repo"
    _repo_with_committed_files(root, {"pkg/mod.py": b"one\n"})
    (root / "pkg" / "mod.py").write_bytes(b"one\r\n")

    measurement = measure(root)
    assert measurement.buckets == {"pkg": 1}

    findings = growth_against_ceiling(measurement, total=5, buckets={"other": 9})

    assert findings == ["pkg/ 1 exceeds the recorded ceiling 0"]
    assert growth_against_ceiling(measurement, total=5, buckets={"pkg": 1}) == []


def test_a_recorded_ceiling_lands_as_untranslated_bytes(tmp_path: Path) -> None:
    """The screen's own baseline is written with pinned terminators.

    A ceiling written through the platform default would enter this screen's
    own worklist on the next run, which is a self-refuting instrument.
    """
    root = tmp_path / "repo"
    _repo_with_committed_files(root, {"mod.py": b"one\n"})
    (root / "mod.py").write_bytes(b"one\r\n")

    target = tmp_path / "checkout_drift_baseline.json"
    assert not target.exists(), "the capture must be what creates the file"

    measurement = measure(root)
    write_ceiling(measurement, head="0" * 40, path=target)

    raw = target.read_bytes()
    assert raw, "the capture wrote an empty file"
    assert b"\r\n" not in raw, "the capture translated its own baseline's terminators"

    total, buckets = load_ceiling(target)
    assert total == measurement.total
    assert buckets == measurement.buckets
    assert json.loads(raw.decode(_UTF_8))["measured_at_head"] == "0" * 40


def test_the_committed_ceiling_is_recorded_and_readable() -> None:
    """The committed ceiling exists, is non-vacuous, and carries pinned terminators.

    Without this the screen could ship with no ceiling at all and its
    ``--check`` mode would compare every run against nothing while still
    exiting 0, which reads exactly like a healthy repository.
    """
    baseline = Path(__file__).resolve().parents[1] / "checkout_drift_baseline.json"
    assert baseline.is_file(), f"the committed ceiling is absent: {baseline}"

    raw = baseline.read_bytes()
    assert b"\r\n" not in raw, "the committed ceiling carries translated terminators"

    total, buckets = load_ceiling(baseline)
    assert total is not None, "the committed ceiling records no total"
    assert buckets, "the committed ceiling records no per-tree counters"
    assert sum(buckets.values()) == total, "the per-tree counters do not reconcile with the total"
