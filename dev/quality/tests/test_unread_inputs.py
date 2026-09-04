"""Tests for the shared unread-input notice.

The notice replaces twelve near-identical blocks across nine dev modules. Its
whole value is that it says the same thing the same way while keeping each
caller's consequence, so the two properties worth pinning are that the
consequence survives verbatim and that silence is preserved when nothing was
skipped.
"""

from __future__ import annotations

import pytest

from ..unread_inputs import format_unread_notice, report_unread

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_nothing_skipped_produces_no_notice() -> None:
    """A notice that fired on every run would tell a reader nothing.

    Returning empty rather than a blank line lets a caller write it
    unconditionally without polluting a clean run's stderr.
    """
    assert format_unread_notice("scanner", "keys would look unused", []) == ""


def test_the_notice_names_the_instrument_the_count_and_the_files() -> None:
    """Several instruments write to one stream, so an unattributed notice is noise."""
    notice = format_unread_notice("scanner", "keys would look unused", ["a.py: boom", "b.py: boom"])

    assert notice.startswith("scanner: 2 input(s) could not be read;")
    assert "a.py" in notice
    assert "b.py" in notice
    assert notice.endswith(chr(10))


def test_the_consequence_survives_verbatim() -> None:
    """The part a reader acts on, and the reason it is a parameter.

    A generic sentence would make every notice interchangeable and remove the
    only content that differs between an inflated finding set and a shrunken
    one.
    """
    consequence = "a symbol only this test imports is listed unreached in error"

    assert consequence in format_unread_notice("reach", consequence, ["x.py: boom"])


def test_the_file_list_is_sorted_so_two_runs_agree() -> None:
    """Notices are compared across runs; an unstable order is noise in every diff."""
    notice = format_unread_notice("scanner", "why", ["zulu.py: boom", "alpha.py: boom"])

    assert notice.index("alpha.py") < notice.index("zulu.py")


def test_reporting_writes_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Findings go to stdout; incompleteness is a diagnostic about the run itself."""
    report_unread("scanner", "keys would look unused", ["a.py: boom"])

    captured = capsys.readouterr()
    assert "keys would look unused" in captured.err
    assert captured.out == ""


def test_reporting_nothing_writes_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """The silent path, asserted so a clean run stays clean."""
    report_unread("scanner", "keys would look unused", [])

    assert capsys.readouterr().err == ""
