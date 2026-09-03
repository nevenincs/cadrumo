"""Real-behaviour tests for the note-label scope screen.

The screen's claim is that a note label identifies a note only with its sheet.
Two things have to hold: it must find the repetition where the corpus really
carries it, and it must not report a design whose labels are unique. The second
is the one a screen counting rows would pass without ever checking.
"""

from __future__ import annotations

import pathlib
from typing import Final

import pytest

from ..analysis.note_label_scope import KINDS, design_findings, screen_corpus, transcription_paths

#: Named once per module rather than repeated at each read site, where a typo
#: would be a silent decode change rather than an error.
_UTF_8: Final[str] = "utf-8"

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _write(tmp_path: pathlib.Path, name: str, body: str) -> pathlib.Path:
    """Write a constructed design under a modelo directory, as the corpus does.

    A finding names the modelo whose corpus directory holds the design, read
    from the path, and a design written outside one is refused rather than given
    an invented modelo.
    """
    directory = tmp_path / "modelo_999" / "files"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body, encoding=_UTF_8)
    return path


def test_a_label_defined_on_two_sheets_is_reported_with_both(tmp_path: pathlib.Path) -> None:
    """The repetition is found, and the row names every sheet defining it.

    Constructed rather than sampled from the corpus, so the screen is shown
    detecting the condition rather than agreeing with whatever the corpus
    currently holds.
    """
    design = _write(
        tmp_path,
        "constructed.xlsx.extracted.md",
        "# SHEETA\nNota 1: primera\n\n# SHEETB\nNota 1: segunda\n",
    )
    findings = design_findings(design)
    assert [item.kind for item in findings] == ["label_repeats_across_sheets"]
    assert findings[0].label == "nota 1"
    assert findings[0].sheets == ("SHEETA", "SHEETB")
    assert findings[0].merged == 1


def test_a_design_whose_labels_are_unique_reports_nothing(tmp_path: pathlib.Path) -> None:
    """No repetition, no finding.

    Without this the screen could report every label it finds and still pass the
    case above, which would make the population meaningless.
    """
    design = _write(
        tmp_path,
        "unique.xlsx.extracted.md",
        "# SHEETA\nNota 1: primera\n\n# SHEETB\nNota 2: segunda\n",
    )
    assert design_findings(design) == ()


def test_a_design_with_no_notes_reports_nothing(tmp_path: pathlib.Path) -> None:
    """Absence of notes is a census figure, never a row.

    It is the majority state, so reporting it per design would bury the rows
    that carry work.
    """
    design = _write(tmp_path, "bare.xlsx.extracted.md", "# SHEETA\n1 | 1 | 2 | An | algo\n")
    assert design_findings(design) == ()


def test_the_merged_count_is_the_surplus_not_the_sheet_count(tmp_path: pathlib.Path) -> None:
    """Three sheets sharing one label would have merged two notes into one.

    The surplus is the number a design-wide reader absorbed. Counting sheets
    instead would overstate every row by one and make the corpus census wrong
    by the number of repeated labels.
    """
    design = _write(
        tmp_path,
        "three.xlsx.extracted.md",
        "# A\nNota 1: uno\n\n# B\nNota 1: dos\n\n# C\nNota 1: tres\n",
    )
    finding = design_findings(design)[0]
    assert len(finding.sheets) == 3
    assert finding.merged == 2


def test_the_bundled_corpus_carries_the_condition() -> None:
    """The screen reads the real corpus and finds the repetition in it.

    Held by presence and by shape rather than by count: the figures move
    whenever a design is added or re-transcribed, and a test pinning them would
    fail on work that changed nothing about the property.
    """
    paths = transcription_paths()
    assert paths, "the screen found no transcriptions, so it measured nothing"
    findings = screen_corpus()
    assert findings, "the condition lost its live population"
    for item in findings:
        assert item.kind in KINDS
        assert len(item.sheets) > 1
        assert item.merged == len(item.sheets) - 1
        assert item.design.endswith(".extracted.md")
