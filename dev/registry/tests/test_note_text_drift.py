"""Real-behaviour tests for the note text drift screen.

The screen must separate three states that all look alike from a distance: a
label appearing once, a label appearing several times with one text, and a label
appearing several times with different texts. Only the third is a finding, and a
screen that confused any two of them would still produce plausible rows.
"""

from __future__ import annotations

import pathlib

import pytest

from ..analysis.note_text_drift import KINDS, note_texts_by_key, screen_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A newline, named so the constructed transcriptions below carry no escape.
LINE_BREAK = chr(10)


def _design(root: pathlib.Path, name: str, *lines: str) -> None:
    """Write a constructed design under a modelo directory, as the corpus does."""
    directory = root / "modelo_999" / "files"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.xlsx.extracted.md").write_text(
        LINE_BREAK.join(lines) + LINE_BREAK, encoding="utf-8"
    )


def test_one_label_with_two_texts_across_designs_is_reported(tmp_path: pathlib.Path) -> None:
    """The condition: the same name, different wording, in two documents."""
    _design(tmp_path, "a", "# S", "Nota 1: primera redaccion")
    _design(tmp_path, "b", "# S", "Nota 1: una redaccion distinta y mas larga")
    findings = screen_corpus(tmp_path)
    assert [item.kind for item in findings] == list(KINDS)
    assert findings[0].sheet == "S"
    assert findings[0].label == "nota 1"
    assert len(findings[0].designs) == 2
    assert len(set(findings[0].lengths)) == 2


def test_one_label_with_the_same_text_everywhere_is_not_reported(tmp_path: pathlib.Path) -> None:
    """Repetition is not drift.

    Eighty-seven of the corpus's shared keys are in this state, so a screen
    reporting repetition rather than difference would bury the twenty-four that
    matter under the majority that do not.
    """
    _design(tmp_path, "a", "# S", "Nota 1: misma redaccion")
    _design(tmp_path, "b", "# S", "Nota 1: misma redaccion")
    assert screen_corpus(tmp_path) == ()


def test_a_label_in_one_design_only_is_not_reported(tmp_path: pathlib.Path) -> None:
    """With one design there is nothing to differ from."""
    _design(tmp_path, "a", "# S", "Nota 1: unica")
    assert screen_corpus(tmp_path) == ()


def test_the_same_label_on_different_sheets_is_not_one_key(tmp_path: pathlib.Path) -> None:
    """Sheet is part of the key, so two pages numbering from one do not collide.

    Without this the screen would report every design that numbers its notes per
    page - which is most of them - as drifting.
    """
    _design(tmp_path, "a", "# S1", "Nota 1: una cosa", "", "# S2", "Nota 1: otra cosa")
    assert screen_corpus(tmp_path) == ()
    keys = note_texts_by_key(tmp_path)
    assert ("999", "S1", "nota 1") in keys
    assert ("999", "S2", "nota 1") in keys


def test_the_bundled_corpus_carries_both_states() -> None:
    """The live corpus has drifting keys and stable ones, and both are found.

    Held by presence rather than by count: the figures move whenever a design is
    added or re-transcribed. What must stay true is that the screen separates
    the two populations rather than reporting one of them.
    """
    by_key = note_texts_by_key()
    shared = {key: texts for key, texts in by_key.items() if len(texts) > 1}
    assert shared, "no note label appears in more than one design, so this proves nothing"
    findings = screen_corpus()
    assert findings, "the condition lost its live population"
    assert len(findings) < len(shared), "every shared key drifts, so the screen is not discriminating"
    for item in findings:
        assert item.kind in KINDS
        assert len(item.designs) == len(item.lengths) > 1
