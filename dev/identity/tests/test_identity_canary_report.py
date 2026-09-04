"""Tests for the identity canary's report shape.

`dev.quality.module_test_reach` listed `dev/identity/__main__.py` as unreached.
It is not one of the thin entry-point shims: it decides what a reader is told
about identity material in this tree, and it is the clearest example in the
repository of the discipline this campaign has spent its time restoring
elsewhere. It prints, in one run, the blocking findings, the operator-tier
occurrences that are expected and do not fail a build, the files it enumerated
but could not open, every path-exclusion with its occurrence count AND its
reason, and the advisory population the blocking scope leaves out - because, in
its own words, the narrowing should stay "visible and arguable rather than
silent".

The live section test drives the real scan over this working tree, which takes
about a hundred seconds; that is the subject, and a stand-in corpus would prove
something about the stand-in. The bucketing rule is exercised directly, since
it decides how the advisory summary reads.
"""

from __future__ import annotations

import pytest

from ..__main__ import _bucket, main

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_a_repository_root_file_is_labelled_as_such() -> None:
    """A bare filename has no directory to summarise under."""
    assert _bucket("pyproject.toml") == "<repository root>"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/cadrumo/domain/thing.py", "src/cadrumo"),
        ("dev/identity/_tree_scan.py", "dev/identity"),
        ("docs/guide/install.md", "docs/guide"),
    ],
)
def test_the_managed_trees_are_summarised_two_levels_deep(path: str, expected: str) -> None:
    """One level would put every source file under a single bucket.

    ``src`` alone says nothing about where identity material clusters, which is
    the only reason the advisory summary is worth printing.
    """
    assert _bucket(path) == expected


@pytest.mark.parametrize("path", ["var/scratch/thing.json", "node_modules/pkg/file.js"])
def test_an_unmanaged_tree_is_summarised_at_its_root(path: str) -> None:
    """Outside the managed trees the top directory is the useful grouping.

    Going deeper there would scatter one external tree across many buckets and
    bury the count that matters.
    """
    assert _bucket(path) == path.split("/")[0]


def test_the_report_carries_every_section_and_its_exit_code_tracks_the_blocking_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Each section exists so a narrowing stays arguable; a missing one hides it.

    The exit code is asserted against what the report itself says rather than a
    pinned verdict, so this holds whether or not the tree currently carries a
    blocking finding.
    """
    exit_code = main()

    out = capsys.readouterr().out
    assert "blocking scope:" in out
    assert "operator tier, untracked and ignored content:" in out
    assert "suppressed by path exclusion" in out
    assert "advisory, outside the blocking scope:" in out

    findings_line = next(line for line in out.splitlines() if line.startswith("blocking scope:"))
    blocking_findings = int(findings_line.split(",")[1].strip().split(" ")[0])
    assert (exit_code == 0) == (blocking_findings == 0)


def test_every_path_exclusion_is_printed_with_a_reason(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A suppression without a stated reason is an exemption nobody can review.

    The count alone would say how much was hidden but not why any of it was.
    """
    from .._tree_scan import EXCLUDED_PATH_FRAGMENTS

    main()

    out = capsys.readouterr().out
    assert EXCLUDED_PATH_FRAGMENTS, "no exclusions declared, so this would prove nothing"
    for fragment, reason in EXCLUDED_PATH_FRAGMENTS.items():
        assert fragment in out
        assert reason in out
