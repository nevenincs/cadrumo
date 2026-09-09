"""The note-pointer screen separates a resolvable citation from an ambiguous one."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..analysis.unresolvable_note_pointers import (
    UnresolvableNotePointer,
    unresolvable_note_pointers,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_field_citing_a_single_text_label_is_resolvable() -> None:
    """One text behind the label means the pointer has one reading."""
    row = UnresolvableNotePointer("999", "2026", "f1", "nota2", distinct_texts=1)

    assert row.is_resolvable


def test_a_field_citing_a_many_text_label_is_not() -> None:
    """Several texts mean the artefact records no reading having been chosen."""
    row = UnresolvableNotePointer("999", "2026", "f1", "nota2", distinct_texts=3)

    assert not row.is_resolvable


def test_a_field_with_no_note_pointer_is_not_reported(tmp_path: Path) -> None:
    """A content cell that states its own meaning cites nothing and needs no note."""
    export = tmp_path / "999" / "revisions" / "2026" / "export"
    export.mkdir(parents=True)
    (export / "_generation.provenance.json").write_text(
        json.dumps(
            {
                "field_derivations": [
                    {
                        "field": {"id": "f1"},
                        "parser_field": {"content": "15 enteros 2 decimales"},
                    },
                ],
            },
        ),
        encoding="utf-8",
    )

    assert not tuple(unresolvable_note_pointers(tmp_path))


def test_the_shipped_corpus_carries_the_measured_population() -> None:
    """The screen must report the population it was built for, not silence.

    A screen reporting nothing across fields it never read is indistinguishable
    from a clean corpus, which is how the sign defect survived every green gate.
    """
    rows = tuple(unresolvable_note_pointers())

    assert rows, "the corpus reports no ambiguous note pointer, which the label census contradicts"
    assert all(not row.is_resolvable for row in rows), "a resolvable pointer must not be reported"
    assert any(row.modelo == "390" and row.note_label == "nota2" for row in rows), (
        "the annual IVA summary's mandated-value slots are the known instance and must appear"
    )
