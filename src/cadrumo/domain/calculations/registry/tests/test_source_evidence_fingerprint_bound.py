"""The source-evidence fingerprint window admits only the immutable tree.

Collecting this fingerprint stats every file under the evidence roots and the
authority collects it on every load, so it is bounded on the same premise the
registry tree fingerprint is: package data is read-only, a caller-supplied
specimen tree is not. The bound is only safe while that distinction holds, so
both halves are pinned here -- a specimen root is never served from the window,
and the bundled root genuinely is, so the bound cannot be quietly made inert.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from .....core.resources import bundled_path
from .. import _source_evidence_fingerprint
from .._source_evidence_fingerprint import (
    clear_source_evidence_fingerprint_cache,
    collect_source_evidence_fingerprints,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write_specimen_evidence(source_root: Path, *, payload: str) -> Path:
    """Materialise (or rewrite) a caller-supplied specimen evidence tree."""
    corpus_dir = source_root / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    specimen = corpus_dir / "specimen.txt"
    specimen.write_text(payload, encoding="utf-8", newline="\n")
    return specimen


def test_a_specimen_evidence_root_is_never_served_from_the_window(tmp_path: Path) -> None:
    """An edit to a caller-supplied evidence tree must reach the very next call.

    A specimen root is exactly the tree a run can rewrite mid-flight, which is
    what the window's immutability premise does not cover. Both calls happen
    well inside the window, so a served entry would return the pre-edit
    fingerprint.
    """
    clear_source_evidence_fingerprint_cache()
    source_root = tmp_path / "specimen"
    _write_specimen_evidence(source_root, payload="before")

    before = collect_source_evidence_fingerprints(source_root)
    assert len(before) == 1, "sanity: the specimen tree must contribute exactly one evidence file"

    _write_specimen_evidence(source_root, payload="a longer payload than before")

    after = collect_source_evidence_fingerprints(source_root)
    assert after != before, (
        "a caller-supplied specimen evidence tree was served a fingerprint that predates the edit on disk"
    )


def test_the_bundled_evidence_root_is_served_from_the_window() -> None:
    """The bundled tree really is bounded, so the bound cannot be made inert.

    Two calls milliseconds apart return the SAME tuple object, which is only
    possible when the second was served rather than re-walked. Without this the
    correctness half above would still pass with the window removed entirely,
    and the cost the window exists to remove would silently come back.
    """
    clear_source_evidence_fingerprint_cache()
    source_root = bundled_path()

    first = collect_source_evidence_fingerprints(source_root)
    second = collect_source_evidence_fingerprints(source_root)

    assert first, "sanity: the bundled evidence corpus must contribute at least one file"
    assert second is first, "the bundled evidence root must be served from the window, not re-walked"


def test_the_bundled_evidence_window_walks_once_before_serving_repeats(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bounded path performs one filesystem walk, then reuses that result."""
    clear_source_evidence_fingerprint_cache()
    source_root = bundled_path()
    original_walk = _source_evidence_fingerprint._walk_source_evidence
    walks = 0

    def observed_walk(roots: tuple[Path, ...]) -> tuple[tuple[str, int, int], ...]:
        nonlocal walks
        walks += 1
        return original_walk(roots)

    monkeypatch.setattr(_source_evidence_fingerprint, "_walk_source_evidence", observed_walk)

    first = collect_source_evidence_fingerprints(source_root)
    second = collect_source_evidence_fingerprints(source_root)

    assert second is first
    assert walks == 1, "a hot bundled lookup must not re-walk the complete evidence corpus"


def test_clearing_the_window_forces_a_fresh_walk() -> None:
    """The clear entry point really empties the window.

    Test isolation depends on it: a module that edits evidence and a module that
    asserts on the bundled fingerprint run in the same process.
    """
    source_root = bundled_path()
    first = collect_source_evidence_fingerprints(source_root)

    clear_source_evidence_fingerprint_cache()

    second = collect_source_evidence_fingerprints(source_root)
    assert second is not first, "clearing the window must force a fresh walk"
    assert second == first, "an unchanged corpus must fingerprint identically across walks"
