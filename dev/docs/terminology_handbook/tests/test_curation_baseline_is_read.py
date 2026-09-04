"""The recorded curation baseline must be read, not merely recorded.

``curation-ratchet.json`` sits beside this package recording a draft count, an
empty-short-description count, a date and a review cadence. Nothing loaded it -
no module, no recipe, no other declaration named the file - so it read as
governance while being inert.

It had already been passed. The file records 99 drafts and 100 empty short
descriptions as of 2026-07-30; the audit it names as its own source reports 101
and 102. Both moved and nothing noticed, because nothing was looking.

The baseline is REPORTED, never enforced. Those numbers are a frozen corpus
count, which this project's quality rule disfavours as proof of anything; what
they can honestly do is show a reader how far the tree has moved since someone
last reviewed it.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ..cli import _CURATION_BASELINE_NAME, _recorded_curation_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_the_recorded_baseline_file_exists_and_is_named_here() -> None:
    """Naming it in source is what stops it being orphaned again.

    The file was unreferenced by anything in the repository, which is precisely
    why nobody noticed it had been passed.
    """
    path = pathlib.Path(__file__).parents[1] / _CURATION_BASELINE_NAME

    assert path.is_file(), "the baseline this module reads is gone; drop the reader with it"


def test_the_baseline_carries_the_counts_the_audit_compares() -> None:
    """A baseline missing its counts would render an unreadable comparison line."""
    baseline = _recorded_curation_baseline()

    assert "draft_count" in baseline
    assert "empty_short_description_count" in baseline
    assert "recorded_at" in baseline


def test_a_missing_baseline_yields_an_empty_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    """An absent baseline must not break the audit that reports it.

    The audit's own findings are the point; a missing review record is a
    degraded report, not a failed one.
    """
    from .. import cli

    monkeypatch.setattr(cli, "_CURATION_BASELINE_NAME", "never-recorded.json")

    assert _recorded_curation_baseline() == {}


def test_a_malformed_baseline_is_reported_rather_than_raised(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Unreadable JSON must not take the audit down with it.

    Written beside the package under a temporary name so the committed baseline
    is never touched.
    """
    from .. import cli

    broken = pathlib.Path(cli.__file__).with_name("broken-baseline-for-test.json")
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(cli, "_CURATION_BASELINE_NAME", broken.name)
    try:
        assert _recorded_curation_baseline() == {}
        assert "could not be read" in capsys.readouterr().out
    finally:
        broken.unlink()


def test_a_non_object_baseline_is_ignored(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A JSON list would fail on every ``.get`` in the comparison line."""
    from .. import cli

    listed = pathlib.Path(cli.__file__).with_name("listed-baseline-for-test.json")
    listed.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    monkeypatch.setattr(cli, "_CURATION_BASELINE_NAME", listed.name)
    try:
        assert _recorded_curation_baseline() == {}
    finally:
        listed.unlink()
