"""The review notes store keeps what a reviewer wrote, and says which images it was about.

Notes outlive the server process and every render, so the checks here reopen
the database the way a restarted server would, rather than trusting the
instance that wrote it.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from .._review_store import (
    NOTE_BODY_LIMIT,
    InvalidNoteError,
    NoteImageState,
    NoteNotFoundError,
    ReviewStore,
    ReviewStoreVersionError,
    SignOff,
    image_state,
    sign_off_changes,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIRST = "a" * 64
_SECOND = "b" * 64
_THIRD = "c" * 64
_ELEMENT = "fixture:home"
_OTHER_ELEMENT = "fixture:ledger-overview"
_FRAME = "home--ready/medium/dark"


def _store(tmp_path: Path) -> ReviewStore:
    return ReviewStore(tmp_path / "review" / "notes.sqlite3")


def test_a_note_is_read_back_by_a_store_opened_afresh_on_the_same_file(tmp_path: Path) -> None:
    written = _store(tmp_path).add_note(
        element_key=_ELEMENT,
        run="current",
        element_sha256=_FIRST,
        frame=(_FRAME, _SECOND),
        body="  The footer wraps at eighty columns.\n",
    )

    reopened = _store(tmp_path).notes()

    assert reopened == (written,)
    assert written.body == "The footer wraps at eighty columns."
    assert (written.element_key, written.element_sha256) == (_ELEMENT, _FIRST)
    assert (written.frame_key, written.frame_sha256) == (_FRAME, _SECOND)
    assert written.resolved_at is None


def test_a_note_about_the_whole_element_points_at_no_frame(tmp_path: Path) -> None:
    written = _store(tmp_path).add_note(element_key=_ELEMENT, run="current", element_sha256=_FIRST, body="Too dense.")

    (reopened,) = _store(tmp_path).notes()

    assert reopened == written
    assert (reopened.frame_key, reopened.frame_sha256) == (None, None)


def test_the_database_refuses_a_frame_pointer_without_its_image(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.ensure()

    with closing(sqlite3.connect(store.path)) as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO note (element_key, run, element_sha256, frame_key, body, created_at) "
            "VALUES (?, 'current', ?, ?, 'x', 'now')",
            (_ELEMENT, _FIRST, _FRAME),
        )


def test_resolving_hides_a_note_from_the_open_list_and_reopening_restores_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    kept = store.add_note(element_key=_ELEMENT, run="current", element_sha256=_FIRST, body="Border is doubled.")
    other = store.add_note(element_key=_OTHER_ELEMENT, run="current", element_sha256=_SECOND, body="Totals misaligned.")

    resolved = store.set_resolved(kept.id, resolved=True)

    assert resolved.resolved_at is not None
    assert _store(tmp_path).notes(include_resolved=False) == (other,)
    assert {note.id for note in _store(tmp_path).notes()} == {kept.id, other.id}

    reopened = store.set_resolved(kept.id, resolved=False)

    assert reopened.resolved_at is None
    assert {note.id for note in _store(tmp_path).notes(include_resolved=False)} == {kept.id, other.id}


def test_notes_are_grouped_by_element_whatever_order_they_were_written_in(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.add_note(element_key=_OTHER_ELEMENT, run="current", element_sha256=_FIRST, body="one")
    store.add_note(element_key=_ELEMENT, run="current", element_sha256=_FIRST, body="two")
    store.add_note(element_key=_OTHER_ELEMENT, run="current", element_sha256=_FIRST, body="three")

    assert [(note.element_key, note.body) for note in _store(tmp_path).notes()] == [
        (_ELEMENT, "two"),
        (_OTHER_ELEMENT, "one"),
        (_OTHER_ELEMENT, "three"),
    ]


def test_a_deleted_note_is_gone_for_every_later_reader(tmp_path: Path) -> None:
    store = _store(tmp_path)
    doomed = store.add_note(element_key=_ELEMENT, run="current", element_sha256=_FIRST, body="Typo in the title.")

    store.delete_note(doomed.id)

    assert _store(tmp_path).notes() == ()


@pytest.mark.parametrize("body", ["", "   ", "\n\t\n", "x" * (NOTE_BODY_LIMIT + 1)])
def test_a_note_with_no_text_or_too_much_is_refused_and_nothing_is_written(tmp_path: Path, body: str) -> None:
    store = _store(tmp_path)

    with pytest.raises(InvalidNoteError):
        store.add_note(element_key=_ELEMENT, run="current", element_sha256=_FIRST, body=body)

    assert store.notes() == ()


def test_a_note_at_the_length_limit_is_kept_whole(tmp_path: Path) -> None:
    body = "y" * NOTE_BODY_LIMIT

    note = _store(tmp_path).add_note(element_key=_ELEMENT, run="current", element_sha256=_FIRST, body=body)

    assert _store(tmp_path).notes()[0].body == body == note.body


def test_changing_a_note_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(NoteNotFoundError):
        store.set_resolved(404, resolved=True)
    with pytest.raises(NoteNotFoundError):
        store.delete_note(404)


def test_a_sign_off_keeps_every_frame_it_covered_and_a_later_one_replaces_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.sign_off(element_key=_ELEMENT, run="current", frames={"a/small/dark": _FIRST, "b/small/dark": _SECOND})
    store.sign_off(element_key=_ELEMENT, run="baseline", frames={"a/small/dark": _THIRD})
    store.sign_off(element_key=_OTHER_ELEMENT, run="current", frames={"c/small/dark": _FIRST})

    marks = _store(tmp_path).sign_offs()

    assert (marks[_ELEMENT].run, marks[_ELEMENT].frames) == ("baseline", {"a/small/dark": _THIRD})
    assert marks[_OTHER_ELEMENT].frames == {"c/small/dark": _FIRST}


def test_clearing_a_sign_off_withdraws_it_and_its_frames(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.sign_off(element_key=_ELEMENT, run="current", frames={"a/small/dark": _FIRST})

    store.clear_sign_off(_ELEMENT)
    store.clear_sign_off("fixture:never-signed-off")

    assert _store(tmp_path).sign_offs() == {}
    with closing(sqlite3.connect(store.path)) as connection:
        assert connection.execute("SELECT count(*) FROM sign_off_frame").fetchone()[0] == 0


def test_an_element_with_no_frame_cannot_be_signed_off(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(ValueError, match="no frame"):
        store.sign_off(element_key=_ELEMENT, run="current", frames={})

    assert store.sign_offs() == {}


def test_a_sign_off_names_each_frame_that_moved_since_it_was_given() -> None:
    mark = SignOff(
        element_key=_ELEMENT,
        run="current",
        reviewed_at="2026-09-29T12:00:00+00:00",
        frames={"kept": _FIRST, "redrawn": _FIRST, "dropped": _FIRST},
    )

    changes = sign_off_changes(mark, {"kept": _FIRST, "redrawn": _SECOND, "arrived": _THIRD})

    assert (changes.changed, changes.added, changes.removed) == (("redrawn",), ("arrived",), ("dropped",))
    assert not changes.unchanged
    assert sign_off_changes(mark, dict(mark.frames)).unchanged


def test_a_store_written_by_another_schema_is_refused_and_left_byte_for_byte(tmp_path: Path) -> None:
    path = tmp_path / "notes.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE note (id INTEGER PRIMARY KEY, text TEXT)")
        connection.execute("PRAGMA user_version = 99")
        connection.commit()
    before = path.read_bytes()

    with pytest.raises(ReviewStoreVersionError, match="99"):
        ReviewStore(path).notes()

    assert path.read_bytes() == before


def test_a_store_of_per_image_sign_offs_is_refused_rather_than_read_as_per_element(tmp_path: Path) -> None:
    path = tmp_path / "notes.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE reviewed (frame_key TEXT PRIMARY KEY, png_sha256 TEXT, reviewed_at TEXT)")
        connection.execute("INSERT INTO reviewed VALUES ('home--ready/small/dark', ?, 'then')", (_FIRST,))
        connection.execute("PRAGMA user_version = 1")
        connection.commit()
    before = path.read_bytes()

    with pytest.raises(ReviewStoreVersionError, match="schema 1"):
        ReviewStore(path).sign_offs()

    assert path.read_bytes() == before


def test_an_unversioned_database_that_already_holds_tables_is_not_adopted(tmp_path: Path) -> None:
    path = tmp_path / "notes.sqlite3"
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("CREATE TABLE something_else (value TEXT)")
        connection.commit()

    with pytest.raises(ReviewStoreVersionError):
        ReviewStore(path).ensure()

    with closing(sqlite3.connect(path)) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"something_else"}


def test_a_new_store_is_only_created_by_use(tmp_path: Path) -> None:
    store = _store(tmp_path)

    assert not store.exists()
    store.ensure()
    assert store.exists()


@pytest.mark.parametrize(
    ("current_digest", "expected"),
    [
        (_FIRST, NoteImageState.CURRENT),
        (_SECOND, NoteImageState.CHANGED),
        (None, NoteImageState.ABSENT),
    ],
)
def test_a_recorded_digest_says_whether_it_describes_what_the_run_holds(
    current_digest: str | None,
    expected: NoteImageState,
) -> None:
    assert image_state(_FIRST, current_digest) is expected
