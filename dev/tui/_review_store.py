"""Durable review notes for the visual inventory, kept outside every run.

A run directory is disposable by contract: `render` rewrites `runs/current`
in place, `snapshot --replace` discards a named run, and the whole run tree is
gitignored as regenerable output. What a reviewer SAYS about those frames is
the opposite -- nothing regenerates it -- so it lives in its own database
beside the run tree rather than inside any run.

Review is per element, not per image: a note or a sign-off is filed under the
element's key, which survives a re-render, and anchored to the element's
digest over every frame it held when the reviewer looked, which does not. A
note may also point at the one frame that was on screen, and a sign-off keeps
the digest of each frame it covered, so a reader can tell which of an
element's images moved since and look at those alone.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
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

STORE_SCHEMA_VERSION: Final[int] = 2
"""Carried in SQLite's ``user_version``. A store written by any other version
is refused rather than guessed at: version 1 filed notes and sign-offs per
image, and an image's sign-off says nothing about the element it belongs to."""

NOTE_BODY_LIMIT: Final[int] = 10_000
"""Characters one note may hold; a review remark, not a document."""

_SCHEMA: Final[tuple[str, ...]] = (
    """
    CREATE TABLE note (
        id INTEGER PRIMARY KEY,
        element_key TEXT NOT NULL,
        run TEXT NOT NULL,
        element_sha256 TEXT NOT NULL,
        frame_key TEXT,
        frame_sha256 TEXT,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        CHECK ((frame_key IS NULL) = (frame_sha256 IS NULL))
    )
    """,
    "CREATE INDEX note_element ON note (element_key)",
    """
    CREATE TABLE sign_off (
        element_key TEXT PRIMARY KEY,
        run TEXT NOT NULL,
        reviewed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE sign_off_frame (
        element_key TEXT NOT NULL,
        frame_key TEXT NOT NULL,
        png_sha256 TEXT NOT NULL,
        PRIMARY KEY (element_key, frame_key)
    )
    """,
)

_NOTE_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "element_key",
    "run",
    "element_sha256",
    "frame_key",
    "frame_sha256",
    "body",
    "created_at",
    "resolved_at",
)
_SELECT_NOTES: Final[str] = (
    "SELECT id, element_key, run, element_sha256, frame_key, frame_sha256, body, created_at, resolved_at FROM note"
)
_SELECT_ALL_NOTES: Final[str] = f"{_SELECT_NOTES} ORDER BY element_key, created_at, id"
_SELECT_OPEN_NOTES: Final[str] = f"{_SELECT_NOTES} WHERE resolved_at IS NULL ORDER BY element_key, created_at, id"
_SELECT_NOTE: Final[str] = f"{_SELECT_NOTES} WHERE id = ?"


class Note(BaseModel):
    """One remark a reviewer left on one element."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: int
    element_key: str
    run: str
    """The run the reviewer was browsing when the note was written."""
    element_sha256: str
    """The element's digest over every frame it held when the note was written."""
    frame_key: str | None = None
    """The frame on screen when the note was written, if the reviewer pointed at it."""
    frame_sha256: str | None = None
    """Digest of that frame's image."""
    body: str
    created_at: str
    resolved_at: str | None = None


class SignOff(BaseModel):
    """An element the reviewer signed off, at the images it held then."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    element_key: str
    run: str
    """The run the reviewer was browsing when they signed off."""
    reviewed_at: str
    frames: dict[str, str]
    """Each frame the sign-off covered, to the digest of its image."""


class NoteImageState(StrEnum):
    """How a recorded digest relates to the images a run holds now."""

    CURRENT = "current"
    """The run holds exactly the images the record was made against."""

    CHANGED = "changed"
    """Something has been re-rendered since; the record may no longer apply."""

    ABSENT = "absent"
    """The run holds no image of what the record names."""


def image_state(recorded_sha256: str, current_sha256: str | None) -> NoteImageState:
    """Say whether a digest recorded with a note or sign-off still describes what a run holds."""
    if current_sha256 is None:
        return NoteImageState.ABSENT
    if current_sha256 == recorded_sha256:
        return NoteImageState.CURRENT
    return NoteImageState.CHANGED


@dataclass(frozen=True)
class SignOffChanges:
    """Which of an element's frames differ from the images its sign-off covered."""

    changed: tuple[str, ...]
    """Frames re-rendered since the sign-off."""
    added: tuple[str, ...]
    """Frames the run holds that the sign-off never saw."""
    removed: tuple[str, ...]
    """Frames the sign-off covered that the run no longer holds."""

    @property
    def unchanged(self) -> bool:
        """Whether the sign-off still covers exactly the images on disk."""
        return not (self.changed or self.added or self.removed)


def sign_off_changes(sign_off: SignOff, current: Mapping[str, str]) -> SignOffChanges:
    """Compare a sign-off with the frames a run holds now for its element, by frame key."""
    covered = sign_off.frames
    return SignOffChanges(
        changed=tuple(sorted(key for key in covered.keys() & current.keys() if covered[key] != current[key])),
        added=tuple(sorted(current.keys() - covered.keys())),
        removed=tuple(sorted(covered.keys() - current.keys())),
    )


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
        """Every note, grouped by element and oldest first within an element."""
        query = _SELECT_ALL_NOTES if include_resolved else _SELECT_OPEN_NOTES
        with self._connect() as connection:
            rows = connection.execute(query).fetchall()
        return tuple(_note(row) for row in rows)

    def add_note(
        self,
        *,
        element_key: str,
        run: str,
        element_sha256: str,
        body: str,
        frame: tuple[str, str] | None = None,
    ) -> Note:
        """Record a note against the element the reviewer was looking at.

        ``frame`` is the key and image digest of the frame on screen, when the
        reviewer points the note at it.
        """
        text = body.strip()
        if not text:
            raise InvalidNoteError("a note needs some text")
        if len(text) > NOTE_BODY_LIMIT:
            raise InvalidNoteError(f"a note holds at most {NOTE_BODY_LIMIT} characters; this one has {len(text)}")
        frame_key, frame_sha256 = frame if frame is not None else (None, None)
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO note (element_key, run, element_sha256, frame_key, frame_sha256, body, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (element_key, run, element_sha256, frame_key, frame_sha256, text, now()),
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

    def sign_offs(self) -> dict[str, SignOff]:
        """Every sign-off, by element key."""
        with self._connect() as connection:
            heads = connection.execute("SELECT element_key, run, reviewed_at FROM sign_off").fetchall()
            covered: dict[str, dict[str, str]] = {}
            for element, frame, digest in connection.execute(
                "SELECT element_key, frame_key, png_sha256 FROM sign_off_frame"
            ):
                covered.setdefault(element, {})[frame] = digest
        return {
            element: SignOff(
                element_key=element,
                run=run,
                reviewed_at=reviewed_at,
                frames=covered.get(element, {}),
            )
            for element, run, reviewed_at in heads
        }

    def sign_off(self, *, element_key: str, run: str, frames: Mapping[str, str]) -> SignOff:
        """Sign an element off at the images it holds; a later sign-off replaces the earlier one."""
        if not frames:
            raise ValueError(f"element {element_key!r} has no frame to sign off")
        mark = SignOff(
            element_key=element_key,
            run=run,
            reviewed_at=now(),
            frames=dict(frames),
        )
        with self._connect() as connection:
            connection.execute("DELETE FROM sign_off_frame WHERE element_key = ?", (element_key,))
            connection.execute(
                "INSERT INTO sign_off (element_key, run, reviewed_at) VALUES (?, ?, ?) "
                "ON CONFLICT (element_key) DO UPDATE SET run = excluded.run, reviewed_at = excluded.reviewed_at",
                (mark.element_key, mark.run, mark.reviewed_at),
            )
            connection.executemany(
                "INSERT INTO sign_off_frame (element_key, frame_key, png_sha256) VALUES (?, ?, ?)",
                [(element_key, key, digest) for key, digest in sorted(mark.frames.items())],
            )
        return mark

    def clear_sign_off(self, element_key: str) -> None:
        """Withdraw an element's sign-off; clearing an unsigned element is a no-op."""
        with self._connect() as connection:
            connection.execute("DELETE FROM sign_off_frame WHERE element_key = ?", (element_key,))
            connection.execute("DELETE FROM sign_off WHERE element_key = ?", (element_key,))


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
    "SignOff",
    "SignOffChanges",
    "image_state",
    "sign_off_changes",
]
