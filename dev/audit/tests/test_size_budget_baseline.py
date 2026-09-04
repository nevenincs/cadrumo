"""Tests for the size-budget baseline reader and writer.

`dev.quality.module_test_reach` listed this module as unreached and writing to
the tree. Unlike the two codemods in `dev/quality`, its writer takes the target
path as an argument, so the write is exercised here on a constructed file rather
than reasoned about - which is the difference between a testable writer and one
that hard-wires its destination.

Two behaviours carry the risk. The reader was emptied when the committed limit
table was retired and must stay empty, or a stale ceiling silently returns. And
the writer preserves hand-written notes across regeneration while dropping those
whose subject is gone, which is the one hand-maintained section in a generated
file - the place where a wrong rule loses prose nobody can recover.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ..size_budget import (
    SizeBudgetBaseline,
    load_size_budget_baseline,
    write_size_budget_baseline,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _baseline(**overrides: object) -> SizeBudgetBaseline:
    fields: dict[str, object] = {
        "modules": {"dev/a.py": 400, "dev/b.py": 200},
        "callables": {"dev/a.py::widen": 60},
        "notes": {},
    }
    fields.update(overrides)
    return SizeBudgetBaseline(**fields)  # type: ignore[arg-type]


def test_the_reader_grandfathers_nothing_whatever_path_it_is_given() -> None:
    """The committed limit table was retired, so every read is empty.

    Pinned because the signature still takes a path and a caller may reasonably
    expect it to be read. A reader that started returning pinned ceilings again
    would restore a ratchet this project deliberately removed, and nothing else
    would say so.
    """
    for path in (None, pathlib.Path("does-not-exist.json")):
        loaded = load_size_budget_baseline() if path is None else load_size_budget_baseline(path)
        assert (loaded.modules, loaded.callables, loaded.notes) == ({}, {}, {})


def test_the_written_document_is_sorted_json_with_a_final_newline(
    tmp_path: pathlib.Path,
) -> None:
    """A generated file is read as a diff, so ordering is part of its contract."""
    target = tmp_path / "budget.json"

    write_size_budget_baseline(
        _baseline(modules={"dev/z.py": 1, "dev/a.py": 2}),
        scanned_modules=2,
        scanned_callables=1,
        path=target,
    )

    text = target.read_text(encoding="utf-8")
    assert text.endswith("\n")
    document = json.loads(text)
    assert list(document["modules"]) == ["dev/a.py", "dev/z.py"]


def test_the_scanned_counts_are_recorded_beside_the_entry_counts(
    tmp_path: pathlib.Path,
) -> None:
    """How many were looked at is a different fact from how many were kept.

    A file recording only its entries cannot distinguish a small tree from a
    scan that stopped early, which is the absence-versus-zero distinction this
    campaign keeps separating.
    """
    target = tmp_path / "budget.json"

    write_size_budget_baseline(_baseline(), scanned_modules=900, scanned_callables=4000, path=target)

    generated = json.loads(target.read_text(encoding="utf-8"))["generated"]
    assert generated == {
        "scanned_modules": 900,
        "scanned_callables": 4000,
        "module_entries": 2,
        "callable_entries": 1,
    }


def test_a_note_whose_subject_survives_is_carried_forward_verbatim(
    tmp_path: pathlib.Path,
) -> None:
    """Notes are the one hand-maintained section of a generated file."""
    target = tmp_path / "budget.json"
    note = "Deliberately large: this module is a generated table."

    write_size_budget_baseline(_baseline(notes={"dev/a.py": note}), scanned_modules=2, scanned_callables=1, path=target)

    assert json.loads(target.read_text(encoding="utf-8"))["notes"] == {"dev/a.py": note}


def test_a_note_whose_subject_is_gone_is_dropped(tmp_path: pathlib.Path) -> None:
    """Prose about a module nobody measures any more explains nothing.

    Keeping it would accumulate commentary on deleted code in a file nobody
    reads top to bottom, which is how a generated artefact becomes unreadable.
    """
    target = tmp_path / "budget.json"

    write_size_budget_baseline(
        _baseline(notes={"dev/a.py": "kept", "dev/deleted.py": "dropped"}),
        scanned_modules=2,
        scanned_callables=1,
        path=target,
    )

    assert json.loads(target.read_text(encoding="utf-8"))["notes"] == {"dev/a.py": "kept"}


def test_a_note_keyed_to_a_callable_survives_too(tmp_path: pathlib.Path) -> None:
    """Both key shapes are live subjects, and only one of them is a path.

    A rule that kept notes for modules alone would silently drop every note
    about a function, which is the half of the table with the finer keys.
    """
    target = tmp_path / "budget.json"

    write_size_budget_baseline(
        _baseline(notes={"dev/a.py::widen": "known long"}),
        scanned_modules=2,
        scanned_callables=1,
        path=target,
    )

    assert json.loads(target.read_text(encoding="utf-8"))["notes"] == {"dev/a.py::widen": "known long"}


def test_the_generated_document_says_it_is_generated(tmp_path: pathlib.Path) -> None:
    """A reader opening it must learn not to hand-edit the numbers."""
    target = tmp_path / "budget.json"

    write_size_budget_baseline(_baseline(), scanned_modules=1, scanned_callables=1, path=target)

    comment = " ".join(json.loads(target.read_text(encoding="utf-8"))["_comment"])
    assert "GENERATED" in comment
    assert "notes" in comment


def test_writing_creates_the_file_and_leaves_nothing_else_behind(
    tmp_path: pathlib.Path,
) -> None:
    """The writer takes its destination, which is why this can be asserted at all.

    Its two siblings in `dev/quality` hard-wire the real tree - one through a
    module constant and one by refusing every path outside it - so neither can
    be exercised writing. This one can.
    """
    target = tmp_path / "nested" / "budget.json"
    target.parent.mkdir()

    write_size_budget_baseline(_baseline(), scanned_modules=1, scanned_callables=1, path=target)

    assert [item.name for item in sorted(tmp_path.rglob("*")) if item.is_file()] == ["budget.json"]
