"""Real-behaviour tests for the unnumbered-note scope evidence.

The screen exists to stop a scope being assumed from where a note is printed.
Its three conditions are proven on constructed designs, and the corpus is then
asserted for the property that actually decides the question - that no design
distinguishes its unnumbered notes by sheet.
"""

from __future__ import annotations

import pathlib

import pytest

from ..analysis.unnumbered_note_scope import KINDS, design_finding, screen_corpus

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A newline, named so the constructed transcriptions below carry no escape.
LINE_BREAK = chr(10)


def _design(tmp_path: pathlib.Path, name: str, *lines: str) -> pathlib.Path:
    """Write a constructed design where the corpus really puts one.

    Under a ``modelo_NNN`` directory, because a finding names the modelo whose
    corpus directory holds it and that is read from the path. A design written
    outside one is refused rather than given an invented modelo, so the fixture
    has to be as faithful about location as about content.
    """
    directory = tmp_path / "modelo_999" / "files"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.xlsx.extracted.md"
    path.write_text(LINE_BREAK.join(lines) + LINE_BREAK, encoding="utf-8")
    return path


def test_one_note_across_several_sheets_is_reported_as_such(tmp_path: pathlib.Path) -> None:
    """A single note in a multi-sheet design cannot be about only its own sheet.

    This is the shape modelo 200 carries, where the note settles how amounts are
    written and its own sheet holds no amount field at all.
    """
    design = _design(
        tmp_path,
        "single",
        "# A",
        "NOTA: Los importes son de 15 enteros y 2 decimales.",
        "# B",
        "Nota 1: otra cosa",
    )
    finding = design_finding(design)
    assert finding is not None
    assert finding.kind == "one_note_many_sheets"
    assert (finding.sheets_with_note, finding.distinct_texts) == (1, 1)


def test_the_same_note_repeated_on_sheets_is_reported_as_repetition(tmp_path: pathlib.Path) -> None:
    """Identical text on several sheets is one statement printed many times."""
    design = _design(tmp_path, "repeat", "# A", "NOTA: El NIF es obligatorio", "# B", "NOTA: El NIF es obligatorio")
    finding = design_finding(design)
    assert finding is not None
    assert finding.kind == "note_on_several_sheets_identical"
    assert (finding.sheets_with_note, finding.distinct_texts) == (2, 1)


def test_differing_notes_across_sheets_are_reported_as_differing(tmp_path: pathlib.Path) -> None:
    """The one shape where the sheet really does distinguish.

    No design in the corpus currently carries it, so it is constructed. Without
    this the screen could collapse every design onto the other two conditions
    and no one would notice the third was unreachable.
    """
    design = _design(tmp_path, "differ", "# A", "NOTA: El NIF es obligatorio", "# B", "NOTA: Otra cosa distinta")
    finding = design_finding(design)
    assert finding is not None
    assert finding.kind == "note_on_several_sheets_differing"
    assert (finding.sheets_with_note, finding.distinct_texts) == (2, 2)


def test_a_design_with_no_unnumbered_note_is_not_reported(tmp_path: pathlib.Path) -> None:
    """Absence is not a finding; the screen reports designs that carry one."""
    assert design_finding(_design(tmp_path, "bare", "# A", "Nota 1: numerada", "1 | 2 | An | x")) is None


def test_no_bundled_design_distinguishes_its_unnumbered_notes_by_sheet() -> None:
    """The corpus property that answers the scope question.

    Every design either prints one such note or repeats one text across sheets.
    Neither supports reading the printing sheet as the note's scope, and no
    design in the corpus supplies a counter-case.

    An earlier measurement did report differing texts, before the reader stopped
    gathering continuation lines. The differences were absorbed neighbours, not
    the design distinguishing anything - which is why this assertion is made
    against the reader that claims only a note's own line.
    """
    findings = screen_corpus()
    assert findings, "no design carries an unnumbered note, so this proves nothing"
    assert all(item.kind in KINDS for item in findings)
    differing = [item for item in findings if item.kind == "note_on_several_sheets_differing"]
    assert differing == []
    # Both observed shapes must actually occur, or the assertion above would
    # hold vacuously on a corpus the reader had stopped reading.
    observed = {item.kind for item in findings}
    assert observed == {"one_note_many_sheets", "note_on_several_sheets_identical"}
