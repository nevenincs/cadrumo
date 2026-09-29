"""The review notes store keeps what a reviewer wrote, and says which image it was about.

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
    Note,
    NoteImageState,
    NoteNotFoundError,
    ReviewStore,
    ReviewStoreVersionError,
    image_state,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIRST_IMAGE = "a" * 64
_SECOND_IMAGE = "b" * 64
_KEY = "home--ready/medium/dark"
_OTHER_KEY = "ledger--ready/small/light"


def _store(tmp_path: Path) -> ReviewStore:
    return ReviewStore(tmp_path / "review" / "notes.sqlite3")


def test_a_note_is_read_back_by_a_store_opened_afresh_on_the_same_file(tmp_path: Path) -> None:
    written = _store(tmp_path).add_note(
        frame_key=_KEY,
        run="current",
        png_sha256=_FIRST_IMAGE,
        body="  The footer wraps at eighty columns.\n",
    )

    reopened = _store(tmp_path).notes()

    assert reopened == (written,)
    assert written.body == "The footer wraps at eighty columns."
    assert written.png_sha256 == _FIRST_IMAGE
    assert written.resolved_at is None


def test_resolving_hides_a_note_from_the_open_list_and_reopening_restores_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    kept = store.add_note(frame_key=_KEY, run="current", png_sha256=_FIRST_IMAGE, body="Border is doubled.")
    other = store.add_note(frame_key=_OTHER_KEY, run="current", png_sha256=_SECOND_IMAGE, body="Totals misaligned.")

    resolved = store.set_resolved(kept.id, resolved=True)

    assert resolved.resolved_at is not None
    assert _store(tmp_path).notes(include_resolved=False) == (other,)
    assert {note.id for note in _store(tmp_path).notes()} == {kept.id, other.id}

    reopened = store.set_resolved(kept.id, resolved=False)

    assert reopened.resolved_at is None
    assert {note.id for note in _store(tmp_path).notes(include_resolved=False)} == {kept.id, other.id}


def test_a_deleted_note_is_gone_for_every_later_reader(tmp_path: Path) -> None:
    store = _store(tmp_path)
    doomed = store.add_note(frame_key=_KEY, run="current", png_sha256=_FIRST_IMAGE, body="Typo in the title.")

    store.delete_note(doomed.id)

    assert _store(tmp_path).notes() == ()


@pytest.mark.parametrize("body", ["", "   ", "\n\t\n", "x" * (NOTE_BODY_LIMIT + 1)])
def test_a_note_with_no_text_or_too_much_is_refused_and_nothing_is_written(tmp_path: Path, body: str) -> None:
    store = _store(tmp_path)

    with pytest.raises(InvalidNoteError):
        store.add_note(frame_key=_KEY, run="current", png_sha256=_FIRST_IMAGE, body=body)

    assert store.notes() == ()


def test_a_note_at_the_length_limit_is_kept_whole(tmp_path: Path) -> None:
    body = "y" * NOTE_BODY_LIMIT

    note = _store(tmp_path).add_note(frame_key=_KEY, run="current", png_sha256=_FIRST_IMAGE, body=body)

    assert _store(tmp_path).notes()[0].body == body == note.body


def test_changing_a_note_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)

    with pytest.raises(NoteNotFoundError):
        store.set_resolved(404, resolved=True)
    with pytest.raises(NoteNotFoundError):
        store.delete_note(404)


def test_a_later_sign_off_replaces_the_earlier_image_and_clearing_withdraws_it(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.mark_reviewed(frame_key=_KEY, png_sha256=_FIRST_IMAGE)
    store.mark_reviewed(frame_key=_KEY, png_sha256=_SECOND_IMAGE)
    store.mark_reviewed(frame_key=_OTHER_KEY, png_sha256=_FIRST_IMAGE)

    marks = _store(tmp_path).reviewed()

    assert marks[_KEY].png_sha256 == _SECOND_IMAGE
    assert marks[_OTHER_KEY].png_sha256 == _FIRST_IMAGE

    store.clear_reviewed(_KEY)
    store.clear_reviewed("never/signed/off")

    assert set(_store(tmp_path).reviewed()) == {_OTHER_KEY}


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
        (_FIRST_IMAGE, NoteImageState.CURRENT),
        (_SECOND_IMAGE, NoteImageState.CHANGED),
        (None, NoteImageState.ABSENT),
    ],
)
def test_a_note_says_whether_it_describes_the_image_on_disk(
    current_digest: str | None,
    expected: NoteImageState,
) -> None:
    note = Note(
        id=1,
        frame_key=_KEY,
        run="current",
        png_sha256=_FIRST_IMAGE,
        body="Colour contrast too low.",
        created_at="2026-09-29T12:00:00+00:00",
    )

    assert image_state(note, current_digest) is expected
