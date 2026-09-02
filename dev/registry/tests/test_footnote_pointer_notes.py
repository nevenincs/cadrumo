"""Real-design tests for resolving a footnote pointer to the note it names."""

from __future__ import annotations

import pathlib

import pytest

from ..analysis.footnote_pointer_notes import (
    POINTER,
    note_definitions,
    resolve_pointer_notes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGN = (
    pathlib.Path("src/cadrumo/_data/corpus/aeat_official/disenos_registro/modelo_353/files")
    / "01-353-ejercicio-2026-y-siguientes-actualizado-03-02-26.xlsx.extracted.md"
)


@pytest.fixture(scope="module")
def definitions() -> dict[str, str]:
    return note_definitions(_DESIGN.read_text(encoding="utf-8"))


def test_the_note_behind_the_known_defect_states_applicability_and_no_wire_fact(
    definitions: dict[str, str],
) -> None:
    """Modelo 353's Nota 4 is quoted, not characterised.

    This is the evidence for the eligibility correction: the field carrying
    ``Nota 4.`` is treated as having its wire fact stated, and the note it points
    at speaks only about which periods the field applies to. It gives no scale,
    no decimal count and no sign convention, so the fact really is unstated.
    """
    resolved = resolve_pointer_notes("Nota 4.", definitions)

    assert [item.note for item in resolved] == ["nota 4"]
    assert resolved[0].text == "Solo para periodos 02 y siguientes."
    for wire_word in ("decimal", "signo", "coma", "cero"):
        assert wire_word not in resolved[0].text.casefold()


def test_a_pointer_naming_several_notes_resolves_each_one(definitions: dict[str, str]) -> None:
    """One cell can name two notes and only one of them may bear on the wire fact."""
    resolved = resolve_pointer_notes("Notas 1 y 2", definitions)

    assert [item.note for item in resolved] == ["nota 1", "nota 2"]
    assert all(item.resolved for item in resolved)
    # Nota 1 carries the numeric conventions; Nota 2 is about declaration type.
    assert "alineados a la derecha" in resolved[0].text
    assert "decimal" not in resolved[1].text.casefold()


def test_accented_note_text_survives_reading(definitions: dict[str, str]) -> None:
    """The Spanish is read intact, because an author relies on the exact wording."""
    assert "Alfabético" in definitions["nota 1"]


def test_a_cell_that_says_more_than_a_pointer_is_not_treated_as_one(
    definitions: dict[str, str],
) -> None:
    """A Contenido cell that states a fact is the design speaking, and stays so.

    The correction this supports narrows what counts as saying nothing. If the
    predicate treated a cell that merely mentions a note as stating nothing, it
    would discard real design statements, which is the opposite failure and the
    worse one.
    """
    for stating in (
        "Importe con 2 decimales. Nota 1",
        'Constante "353"',
        "Num\u00e9rico con signo, ver Nota 3 para el detalle",
    ):
        assert not POINTER.match(stating.strip().rstrip("."))
        assert resolve_pointer_notes(stating, definitions) == ()


def test_an_unresolvable_pointer_is_reported_rather_than_dropped(definitions: dict[str, str]) -> None:
    """A note the design does not define comes back empty and says so."""
    resolved = resolve_pointer_notes("Nota 99", definitions)

    assert [item.note for item in resolved] == ["nota 99"]
    assert not resolved[0].resolved


def test_the_transcription_path_comes_from_the_design_the_source_names() -> None:
    """A design's transcription is derived from its own path, never found by searching.

    Modelo 303 bundles fifteen designs in one directory. A search returns an
    arbitrary sibling, and an earlier measurement that did exactly that reported
    six modelo 303 fields as having unresolvable notes when their own design
    defines twenty-four. Resolving a note against the wrong year's design is
    worse evidence than none, because it still produces a plausible answer.
    """
    from ..analysis.footnote_pointer_notes import design_transcription_path

    assert design_transcription_path(_DESIGN.with_suffix("")).name.endswith(".extracted.md")
    assert design_transcription_path(pathlib.Path("a/b/design.xlsx")) == pathlib.Path("a/b/design.xlsx.extracted.md")


def test_pointer_evidence_separates_a_note_about_the_wire_from_one_about_periods() -> None:
    """The reading aid points an author at the notes worth opening first."""
    from ..analysis.footnote_pointer_notes import pointer_evidence_for_design

    evidence = pointer_evidence_for_design(["Nota 4.", "Nota 1", 'Constante "353"'], _DESIGN)
    by_cell = {item.cell: item for item in evidence}

    assert set(by_cell) == {"Nota 4.", "Nota 1"}, "a cell stating a fact is not pointer evidence"
    assert not by_cell["Nota 4."].mentions_wire_vocabulary, "Nota 4 is about periods"
    assert by_cell["Nota 1"].mentions_wire_vocabulary, "Nota 1 gives the numeric conventions"
    assert by_cell["Nota 4."].unresolved == ()


def test_a_design_with_no_transcription_yields_nothing_and_is_the_callers_problem() -> None:
    """Thirteen bundled designs ship without extracted text, so this case is real.

    Returning nothing is correct here and dangerous if unreported: it is
    indistinguishable from a design that genuinely carries no pointer. The caller
    is expected to check the transcription exists, which is why this returns
    empty rather than raising.
    """
    from ..analysis.footnote_pointer_notes import pointer_evidence_for_design

    assert pointer_evidence_for_design(["Nota 1"], pathlib.Path("no/such/design.xlsx.extracted.md")) == ()
