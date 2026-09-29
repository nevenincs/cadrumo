"""Durable review notes for the visual inventory, kept outside every run.

A run directory is disposable by contract: `render` rewrites `runs/current`
in place, `snapshot --replace` discards a named run, and the whole run tree is
gitignored as regenerable output. What a reviewer SAYS about those frames is
the opposite -- nothing regenerates it -- so it lives in its own database
beside the run tree rather than inside any run.

A note is keyed by the frame's identity (`surface/viewport/theme`), which
survives a re-render, and anchored to the digest of the PNG the reviewer was
looking at, which does not. The pair is what lets a reader tell a note about
the image on screen from a note about an image that has since been replaced.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict

from dev._paths import REPO_ROOT

from ._artifacts import now

REVIEW_STORE_PATH: Final[Path] = REPO_ROOT / ".tui-review" / "notes.sqlite3"
"""Where review notes persist. Gitignored, and outside the run tree on purpose.

The ``.sqlite3`` suffix is also what the worktree clean treats as local state
it must never remove, wherever the file sits."""

STORE_SCHEMA_VERSION: Final[int] = 1
"""Carried in SQLite's ``user_version``. A store written by any other version
is refused rather than guessed at."""

NOTE_BODY_LIMIT: Final[int] = 10_000
"""Characters one note may hold; a review remark, not a document."""

_SCHEMA: Final[tuple[str, ...]] = (
    """
    CREATE TABLE note (
        id INTEGER PRIMARY KEY,
        frame_key TEXT NOT NULL,
        run TEXT NOT NULL,
        png_sha256 TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT
    )
    """,
    "CREATE INDEX note_frame ON note (frame_key)",
    """
    CREATE TABLE reviewed (
        frame_key TEXT PRIMARY KEY,
        png_sha256 TEXT NOT NULL,
        reviewed_at TEXT NOT NULL
    )
    """,
)

_NOTE_FIELDS: Final[tuple[str, ...]] = ("id", "frame_key", "run", "png_sha256", "body", "created_at", "resolved_at")

_SELECT_ALL_NOTES: Final[str] = (
    "SELECT id, frame_key, run, png_sha256, body, created_at, resolved_at FROM note ORDER BY frame_key, created_at, id"
)
_SELECT_OPEN_NOTES: Final[str] = (
    "SELECT id, frame_key, run, png_sha256, body, created_at, resolved_at FROM note "
    "WHERE resolved_at IS NULL ORDER BY frame_key, created_at, id"
)
_SELECT_NOTE: Final[str] = "SELECT id, frame_key, run, png_sha256, body, created_at, resolved_at FROM note WHERE id = ?"


class Note(BaseModel):
    """One remark a reviewer left on one frame."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int
    frame_key: str
    run: str
    """The run the reviewer was browsing when the note was written."""
    png_sha256: str
    """Digest of the image the note was written against."""
    body: str
    created_at: str
    resolved_at: str | None = None


class ReviewedMark(BaseModel):
    """A frame the reviewer signed off, at the image they signed off."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    frame_key: str
    png_sha256: str
    reviewed_at: str


class NoteImageState(StrEnum):
    """How a note relates to the image a run currently holds for its frame."""

    CURRENT = "current"
    """The note was written against the image on disk now."""

    CHANGED = "changed"
    """The frame has been re-rendered since; the note may no longer apply."""

    ABSENT = "absent"
    """The run holds no image for the note's frame."""


def image_state(note: Note, current_digest: str | None) -> NoteImageState:
    """Say whether ``note`` still describes the image a run holds for its frame."""
    if current_digest is None:
        return NoteImageState.ABSENT
    if current_digest == note.png_sha256:
        return NoteImageState.CURRENT
    return NoteImageState.CHANGED


class ReviewStoreVersionError(RuntimeError):
    """The notes database was written by a different version of this tool."""


class NoteNotFoundError(LookupError):
    """No note carries the requested identifier."""


class InvalidNoteError(ValueError):
    """A note body this store refuses to record."""


class ReviewStore:
    """The notes database, opened per operation.

    Each call opens and closes its own connection, so the server's request
    threads and a concurrent ``notes`` command never share one. The default
    rollback journal is kept deliberately: write-ahead logging would leave
    ``-wal`` and ``-shm`` sidecars whose names the worktree clean does not
    recognise as local state.
    """

    def __init__(self, path: Path = REVIEW_STORE_PATH) -> None:
        """Bind the store to ``path``; nothing is created until first use."""
        self.path = path

    def exists(self) -> bool:
        """Whether a notes database has been created at this path yet."""
        return self.path.is_file()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            with connection:
                _ensure_schema(connection, self.path)
                yield connection
        finally:
            connection.close()

    def ensure(self) -> None:
        """Create the database if absent, and refuse one of a foreign schema."""
        with self._connect():
            pass

    def notes(self, *, include_resolved: bool = True) -> tuple[Note, ...]:
        """Every note, grouped by frame and oldest first within a frame."""
        query = _SELECT_ALL_NOTES if include_resolved else _SELECT_OPEN_NOTES
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return tuple(_note(row) for row in rows)

    def add_note(self, *, frame_key: str, run: str, png_sha256: str, body: str) -> Note:
        """Record a note against the image the reviewer was looking at."""
        text = body.strip()
        if not text:
            raise InvalidNoteError("a note needs some text")
        if len(text) > NOTE_BODY_LIMIT:
            raise InvalidNoteError(f"a note holds at most {NOTE_BODY_LIMIT} characters; this one has {len(text)}")
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO note (frame_key, run, png_sha256, body, created_at) VALUES (?, ?, ?, ?, ?)",
                (frame_key, run, png_sha256, text, now()),
            )
            return _read_note(connection, cursor.lastrowid)

    def set_resolved(self, note_id: int, *, resolved: bool) -> Note:
        """Resolve a note, or reopen a resolved one."""
        with self._connect() as connection:
            stamp = now() if resolved else None
            cursor = connection.execute("UPDATE note SET resolved_at = ? WHERE id = ?", (stamp, note_id))
            if cursor.rowcount == 0:
                raise NoteNotFoundError(f"no note #{note_id}")
            return _read_note(connection, note_id)

    def delete_note(self, note_id: int) -> None:
        """Remove a note outright."""
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM note WHERE id = ?", (note_id,))
            if cursor.rowcount == 0:
                raise NoteNotFoundError(f"no note #{note_id}")

    def reviewed(self) -> dict[str, ReviewedMark]:
        """Every sign-off, by frame key."""
        with self._connect() as connection:
            rows = connection.execute("SELECT frame_key, png_sha256, reviewed_at FROM reviewed").fetchall()
        return {row[0]: ReviewedMark(frame_key=row[0], png_sha256=row[1], reviewed_at=row[2]) for row in rows}

    def mark_reviewed(self, *, frame_key: str, png_sha256: str) -> ReviewedMark:
        """Sign a frame off at one image; a later sign-off replaces the earlier one."""
        mark = ReviewedMark(frame_key=frame_key, png_sha256=png_sha256, reviewed_at=now())
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO reviewed (frame_key, png_sha256, reviewed_at) VALUES (?, ?, ?) "
                "ON CONFLICT (frame_key) DO UPDATE SET png_sha256 = excluded.png_sha256, "
                "reviewed_at = excluded.reviewed_at",
                (mark.frame_key, mark.png_sha256, mark.reviewed_at),
            )
        return mark

    def clear_reviewed(self, frame_key: str) -> None:
        """Withdraw a frame's sign-off; clearing an unsigned frame is a no-op."""
        with self._connect() as connection:
            connection.execute("DELETE FROM reviewed WHERE frame_key = ?", (frame_key,))


def _ensure_schema(connection: sqlite3.Connection, path: Path) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version == STORE_SCHEMA_VERSION:
        return
    has_tables = connection.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
    if version != 0 or has_tables:
        message = (
            f"the review notes at {path} carry schema {version}, but this tool reads "
            f"{STORE_SCHEMA_VERSION}. Nothing was changed; move the file aside to start a new store."
        )
        raise ReviewStoreVersionError(message)
    for statement in _SCHEMA:
        connection.execute(statement)
    connection.execute(f"PRAGMA user_version = {STORE_SCHEMA_VERSION}")


def _read_note(connection: sqlite3.Connection, note_id: int | None) -> Note:
    row = connection.execute(_SELECT_NOTE, (note_id,)).fetchone()
    if row is None:
        raise NoteNotFoundError(f"no note #{note_id}")
    return _note(row)


def _note(row: tuple[object, ...]) -> Note:
    return Note.model_validate(dict(zip(_NOTE_FIELDS, row, strict=True)))


__all__ = [
    "NOTE_BODY_LIMIT",
    "REVIEW_STORE_PATH",
    "STORE_SCHEMA_VERSION",
    "InvalidNoteError",
    "Note",
    "NoteImageState",
    "NoteNotFoundError",
    "ReviewStore",
    "ReviewStoreVersionError",
    "ReviewedMark",
    "image_state",
]
