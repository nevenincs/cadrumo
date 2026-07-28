"""Prove the complexity baseline lands as the bytes it serialised.

The committed baseline is a gate INPUT: ``dev.audit.complexity`` reads it to
decide which hotspots are grandfathered debt. When the capture writes through
the platform's newline translation, the bytes the gate reads stop matching the
bytes that were reviewed and committed, and nothing reports it -- the
repository's ``.gitattributes`` normalises to LF on the index side, so
``git diff`` is silent, and every reader of the file goes through a
universal-newline text open that folds the difference away before comparison.

That was the live state, not a hypothesis. Measured on 2026-07-28, before the
writer carried an explicit newline:

    dev/audit/complexity_baseline.json
      disk CRLF=660 LF=660 bytes=66087
      HEAD CRLF=0   LF=660 bytes=65427
      identical=False

Both cases below drive the real :func:`write_baseline` against a temporary
path, so the shipped baseline is never a test subject.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ..complexity import Baseline, load_baseline, write_baseline

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _sample_baseline() -> Baseline:
    """Return a small populated baseline covering all three score families."""
    return Baseline(
        cyclomatic={"dev/example.py::alpha": 12, "dev/example.py::beta": 9},
        maintainability={"dev/example.py": 41.5},
        cognitive={"dev/example.py::alpha": 30},
    )


def test_a_recorded_baseline_lands_as_untranslated_bytes(tmp_path: Path) -> None:
    """The capture writes line feeds and reloads to the baseline it was given.

    The absence assertion up front matters: a capture that silently wrote
    nothing would satisfy a terminator check vacuously, so the file's
    non-existence beforehand and its content afterwards are both asserted.
    """
    target = tmp_path / "complexity_baseline.json"
    assert not target.exists(), "the capture must be what creates the file"

    baseline = _sample_baseline()
    write_baseline(baseline, is_test_run=False, path=target)

    raw = target.read_bytes()
    assert raw, "the capture wrote an empty file"
    assert b"\r\n" not in raw, "the capture translated the file's terminators"
    assert raw.count(b"\n") > 1, "a single-line payload would make the terminator check vacuous"

    assert load_baseline(is_test_run=False, path=target) == baseline


def test_recording_one_scope_leaves_the_other_scope_untranslated(tmp_path: Path) -> None:
    """A second capture rewrites the whole document without translating it.

    The writer re-reads and re-emits the sibling scope on every run, so a
    translating write corrupts terminators for a scope the operator never
    asked to re-record. This is the path by which a ``--tests`` run drifts the
    production section.
    """
    target = tmp_path / "complexity_baseline.json"
    production = _sample_baseline()
    write_baseline(production, is_test_run=False, path=target)

    tests_scope = Baseline(
        cyclomatic={"dev/tests/example.py::gamma": 15},
        maintainability={},
        cognitive={},
    )
    write_baseline(tests_scope, is_test_run=True, path=target)

    raw = target.read_bytes()
    assert b"\r\n" not in raw, "the second capture translated the terminators of both scopes"

    assert load_baseline(is_test_run=False, path=target) == production
    assert load_baseline(is_test_run=True, path=target) == tests_scope


def test_the_committed_audit_baselines_carry_untranslated_terminators() -> None:
    """Neither committed audit baseline on disk carries a translated terminator.

    The two cases above only measure files a test just wrote, so they would
    have left the real artefacts in their drifted state indefinitely. This
    reads the committed files themselves, which is the read nothing in the
    tree performed.

    The size-budget baseline is included even though its writer lives outside
    this package: this file is where both artefacts are read from, and a
    reader that covers only the writer it owns leaves the sibling artefact
    with no reader at all.

    The carriage-return assertion is decisive only on a platform whose line
    separator is not already LF, which is where the drift was measured; on a
    line-feed platform it holds trivially and costs nothing.
    """
    audit_dir = Path(__file__).resolve().parents[1]
    baselines = [
        audit_dir / "complexity_baseline.json",
        audit_dir / "size_budget_baseline.json",
    ]

    translated: list[str] = []
    for baseline in baselines:
        assert baseline.is_file(), f"expected committed baseline is absent: {baseline}"
        raw = baseline.read_bytes()
        assert raw, f"committed baseline is empty, so this gate scanned nothing: {baseline}"
        if b"\r\n" in raw:
            translated.append(baseline.name)

    assert not translated, (
        f"committed audit baselines carry translated terminators: {translated}; "
        f"their on-disk bytes differ from their committed bytes and no diff can show it"
    )
