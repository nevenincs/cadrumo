"""Tests for the silent checkout-drift screen.

`dev.quality.module_test_reach` listed `dev/audit/checkout_drift.py` as unreached
and writing to the tree, and testing it found the screen contradicting itself.
``load_ceiling`` returns no ceiling by design - the ratchet was retired because
the population is contributors' editors, not a generator this repository owns -
but ``growth_against_ceiling`` still compared every tree against an implicit
zero. So ``--check`` exited 1 naming ten trees as exceeding ``the recorded
ceiling 0`` in the same run that printed ``no ceiling is recorded or accepted``,
and the advisory dimension that consumes the same pair reported RED where its
own docstring says AMBER. The module's header names that exact failure - a
ratchet pinned to the population - as the thing it refuses to be.

``blob_hash`` is checked against ``git hash-object``, which is the real oracle
rather than a digest this file computed the same way the module does. That
matters more here than usual: the whole measurement is a comparison against
names git produced, so a hash that agreed only with itself would report a
drifted tree as clean and never say a word.

Every measurement case runs against a scratch repository built for it, so the
screen is driven through real git plumbing on real files rather than a
rearranged substitute.
"""

from __future__ import annotations

import pathlib
import subprocess

import pytest

from ..checkout_drift import (
    DriftMeasurement,
    blob_hash,
    committed_blobs,
    growth_against_ceiling,
    load_ceiling,
    locally_modified,
    measure,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _run(root: pathlib.Path, *arguments: str) -> None:
    subprocess.run(("git", *arguments), cwd=root, check=True, capture_output=True)  # noqa: S603, S607


@pytest.fixture
def repository(tmp_path: pathlib.Path) -> pathlib.Path:
    """Return a scratch repository with one committed LF file.

    It declares ``* text=auto eol=lf`` because the repository under measurement
    does, and that declaration is what MAKES the class silent: git normalises on
    the index side, so a CRLF working copy compares equal to its committed blob
    and ``git diff`` says nothing. A fixture that disabled the filter instead
    would have git report the rewrite as an ordinary modification, and there
    would be no silent drift left for the screen to find.
    """
    _run(tmp_path, "init", "-q")
    _run(tmp_path, "config", "core.autocrlf", "false")
    _run(tmp_path, "config", "user.email", "screen@example.invalid")
    _run(tmp_path, "config", "user.name", "Drift Screen")
    (tmp_path / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    (tmp_path / "committed.txt").write_bytes(b"first\nsecond\n")
    _run(tmp_path, "add", "-A")
    _run(tmp_path, "commit", "-qm", "seed")
    return tmp_path


def _rewrite(path: pathlib.Path, data: bytes) -> None:
    path.write_bytes(data)


def test_the_blob_name_matches_the_one_git_computes(repository: pathlib.Path) -> None:
    """An independent oracle, because everything downstream compares against git.

    A hash that agreed only with itself would call every file clean, and the
    screen would report a healthy number over a drifted tree forever.
    """
    data = b"first\nsecond\n"

    observed = (
        subprocess.run(  # noqa: S603, S607
            ("git", "hash-object", "--stdin"),
            cwd=repository,
            input=data,
            capture_output=True,
            check=True,
        )
        .stdout.decode("ascii")
        .strip()
    )

    assert blob_hash(data) == observed


def test_the_blob_name_distinguishes_terminators(repository: pathlib.Path) -> None:
    """CRLF and LF are different bytes, which is the entire premise here."""
    assert blob_hash(b"first\r\nsecond\r\n") != blob_hash(b"first\nsecond\n")


def test_an_untouched_checkout_reports_no_drift(repository: pathlib.Path) -> None:
    """The clean case, and it must be clean for the right reason."""
    measurement = measure(repository)

    assert measurement.drifted == ()
    assert measurement.scanned > 0, "a screen that hashed nothing reports the same total as a healthy one"


def test_a_file_rewritten_with_crlf_after_checkout_is_found(repository: pathlib.Path) -> None:
    """The defect the module exists for: git stays silent and every text reader folds it away."""
    _rewrite(repository / "committed.txt", b"first\r\nsecond\r\n")

    measurement = measure(repository)

    assert measurement.drifted == ("committed.txt",)
    assert measurement.carrying_crlf == 1


def test_git_itself_reports_that_rewritten_file_as_unmodified(repository: pathlib.Path) -> None:
    """The silence is the finding, so it is asserted rather than assumed.

    Without this the previous case would pass just as well against an ordinary
    uncommitted edit, and the screen's whole subject is the edits git hides.
    """
    _rewrite(repository / "committed.txt", b"first\r\nsecond\r\n")

    assert locally_modified(repository) == set()


def test_an_ordinary_uncommitted_edit_is_excluded(repository: pathlib.Path) -> None:
    """Contributors' live work is not a finding, and it is most of a shared tree."""
    _rewrite(repository / "committed.txt", b"first\nsecond\nthird\n")

    assert locally_modified(repository) == {"committed.txt"}
    assert measure(repository).drifted == ()


def test_a_deleted_file_is_skipped_rather_than_counted_as_drift(repository: pathlib.Path) -> None:
    """A path present at HEAD and absent on disk has no bytes to compare."""
    (repository / "second.txt").write_bytes(b"kept\n")
    _run(repository, "add", "-A")
    _run(repository, "commit", "-qm", "second")
    (repository / "second.txt").unlink()

    measurement = measure(repository)

    assert measurement.drifted == ()
    assert measurement.scanned == 2, "the deleted path was hashed, or the survivors were not"


def test_the_committed_blob_map_carries_every_tracked_path(repository: pathlib.Path) -> None:
    """The map is the denominator; a short read reports a smaller, cleaner number."""
    blobs = committed_blobs(repository)

    assert set(blobs) == {".gitattributes", "committed.txt"}
    assert blobs["committed.txt"] == blob_hash(b"first\nsecond\n")


def test_a_tree_with_nothing_committed_refuses_rather_than_reporting_clean(
    tmp_path: pathlib.Path,
) -> None:
    """A screen that scanned an empty tree reports what a healthy one reports."""
    _run(tmp_path, "init", "-q")

    with pytest.raises(SystemExit):
        measure(tmp_path)


def test_no_ceiling_is_recorded_whatever_path_is_given() -> None:
    """The ratchet was retired deliberately; a returning pin would be a regression."""
    assert load_ceiling() == (None, {})
    assert load_ceiling(pathlib.Path("does-not-exist.json")) == (None, {})


def _measurement(*paths: str) -> DriftMeasurement:
    return DriftMeasurement(tracked=100, scanned=100, drifted=paths, carrying_crlf=0)


def test_an_absent_ceiling_yields_no_growth_at_all() -> None:
    """Nothing to move away from, so nothing moved.

    The defect: each tree was compared against an implicit zero, so every
    populated bucket was reported as a breach. `--check` exited 1 over 2403
    files while printing that no ceiling was recorded, and the advisory
    dimension went RED where its contract says AMBER.
    """
    measurement = _measurement("src/a.py", "dev/b.py", "docs/c.md")

    assert growth_against_ceiling(measurement, None, {}) == []


def test_growth_is_still_reported_against_a_ceiling_that_exists() -> None:
    """Removing the phantom breach must not remove the real one."""
    measurement = _measurement("src/a.py", "src/b.py", "src/c.py")

    growth = growth_against_ceiling(measurement, 2, {"src": 2})

    assert any("total 3 exceeds" in line for line in growth)
    assert any("src/ 3 exceeds" in line for line in growth)


def test_a_tree_absent_from_a_recorded_ceiling_is_compared_against_zero() -> None:
    """Within a ceiling, a newly drifted tree is growth, not an unmeasured pass."""
    measurement = _measurement("src/a.py", "packaging/b.py")

    growth = growth_against_ceiling(measurement, 5, {"src": 4})

    assert growth == ["packaging/ 1 exceeds the recorded ceiling 0"]


def test_shrinking_under_a_recorded_ceiling_is_not_growth() -> None:
    """The shrink-only direction is the point of a ratchet."""
    assert growth_against_ceiling(_measurement("src/a.py"), 4, {"src": 4}) == []
