"""Observe the checkout files and directory listings a sequence's processes actually read.

A documented sequence runs the CLI in the checking interpreter and its profile
workers in child interpreters. Each process that runs under observation
installs a Python audit hook before it imports any product module. The hook
captures the checkout files it opens (source and bytecode imports, data files,
SQLite databases) and the directories it lists. Each file and listing is hashed
the first time it is seen, before the read it announces proceeds. So the
recorded digest is the content the process consumed, and a later edit is a
mismatch rather than a silent pass.

This module is imported first by the observed entry points, so it uses the
standard library only.

What the hook cannot see is reported, never guessed:

- a module imported before the hook whose file changed after the process
  started;
- a listing addressed by file descriptor;
- an unreadable observed file;
- a worker journal that never began, or that says it is incomplete.

Each makes the observation incomplete, and the verdict cache then keys the
sequence on the whole product source instead. A bare existence probe
(``Path.exists``) raises no audit event. It is covered when the probed
directory is otherwise read or listed, because the listing of every observed
file's directory is recorded too.
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Final, TextIO

#: The directory, beside a sandbox's profile storage root, that collects worker journals.
JOURNAL_DIRECTORY_NAME: Final[str] = "docs-dependency-observations"
#: The observed worker script's name, in the checkout and as copied beside the journals.
WORKER_SCRIPT_NAME: Final[str] = "observed_worker.py"
_JOURNAL_SUFFIX: Final[str] = ".journal"
_BEGIN: Final[str] = "B"
_FILE: Final[str] = "F"
_LISTING: Final[str] = "D"
_INCOMPLETE: Final[str] = "X"
_BYTECODE_DIRECTORY: Final[str] = "__pycache__"
_WRITE_FLAGS: Final[int] = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
_ABSENT: Final[str] = "absent"
#: Checkout trees that hold environments, scratch, build output and caches, never verdict inputs.
STRUCTURAL_EXCLUSIONS: Final[tuple[str, ...]] = (".venv", ".tmp", "build", "node_modules", ".git", ".cache")


def _is_read(mode: object, flags: object) -> bool:
    if isinstance(mode, str):
        return not any(letter in mode for letter in "wax+")
    return not (isinstance(flags, int) and flags & _WRITE_FLAGS)


def _source_of(path: Path) -> Path:
    """Map ``pkg/__pycache__/mod.cpython-313.pyc`` to the ``pkg/mod.py`` it was compiled from."""
    if path.parent.name != _BYTECODE_DIRECTORY or path.suffix != ".pyc":
        return path
    return path.parent.parent / f"{path.name.split('.', 1)[0]}.py"


def file_digest(path: Path) -> str:
    """Return the SHA-256 of ``path``'s bytes, or ``absent`` when it is not a readable file."""
    try:
        with path.open("rb") as handle:
            return hashlib.file_digest(handle, "sha256").hexdigest()
    except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError):
        return _ABSENT


def listing_digest(directory: Path) -> str:
    """Return the digest of ``directory``'s sorted entry names, bytecode caches excluded."""
    try:
        names = sorted(name for name in os.listdir(directory) if name != _BYTECODE_DIRECTORY)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return _ABSENT
    return hashlib.sha256("\n".join(names).encode("utf-8", "surrogateescape")).hexdigest()


class Observation:
    """The checkout files and listings one process consumed, each with its first-seen digest."""

    def __init__(self, root: Path, *, started_ns: int) -> None:
        self.root = root.resolve()
        self._excluded = tuple(self.root / name for name in STRUCTURAL_EXCLUSIONS)
        self.started_ns = started_ns
        self.files: dict[Path, str] = {}
        self.listings: dict[Path, str] = {}
        self.incomplete: list[str] = []
        self._journal: TextIO | None = None
        self._lock = threading.RLock()
        self._busy = threading.local()

    def _admitted(self, path: Path) -> bool:
        return path.is_relative_to(self.root) and not any(path.is_relative_to(excluded) for excluded in self._excluded)

    def attach_journal(self, journal: TextIO) -> None:
        """Stream every later observation to ``journal`` as it happens, so a killed worker loses nothing it read."""
        with self._lock:
            self._journal = journal
            journal.write(f"{_BEGIN}\t-\t{os.getpid()}\n")
            for path, digest in self.files.items():
                self._write(_FILE, digest, path)
            for directory, digest in self.listings.items():
                self._write(_LISTING, digest, directory)
            for reason in self.incomplete:
                self._write(_INCOMPLETE, "-", reason)
            journal.flush()

    def _write(self, kind: str, digest: str, path: Path | str) -> None:
        if self._journal is not None:
            self._journal.write(f"{kind}\t{digest}\t{path}\n")
            self._journal.flush()

    def note_file(self, raw: str) -> None:
        path = _source_of(Path(os.path.abspath(raw)))
        if path in self.files or not self._admitted(path):
            return
        digest = file_digest(path)
        with self._lock:
            if path in self.files:
                return
            self.files[path] = digest
            self._write(_FILE, digest, path)
        self.note_listing(str(path.parent))

    def note_listing(self, raw: str) -> None:
        directory = Path(os.path.abspath(raw))
        if directory in self.listings or not self._admitted(directory):
            return
        digest = listing_digest(directory)
        with self._lock:
            if directory in self.listings:
                return
            self.listings[directory] = digest
            self._write(_LISTING, digest, directory)

    def note_incomplete(self, reason: str) -> None:
        with self._lock:
            self.incomplete.append(reason)
            self._write(_INCOMPLETE, "-", reason.replace("\t", " ").replace("\n", " "))

    @contextmanager
    def suspended(self) -> Generator[None]:
        """Stop recording on this thread: the observer's and the cache's own reads are not product inputs."""
        previous = getattr(self._busy, "active", False)
        self._busy.active = True
        try:
            yield
        finally:
            self._busy.active = previous

    def audit(self, event: str, arguments: tuple[object, ...]) -> None:
        """The audit hook: record reads and listings, never re-entering itself."""
        if getattr(self._busy, "active", False):
            return
        with self.suspended():
            try:
                self._dispatch(event, arguments)
            except Exception as error:  # an observer fault must not change the observed program
                self.note_incomplete(f"observer fault on {event}: {type(error).__name__}")

    def _dispatch(self, event: str, arguments: tuple[object, ...]) -> None:
        if event == "open":
            path, mode, flags = arguments[0], arguments[1], arguments[2]
            if isinstance(path, (str, bytes, os.PathLike)) and _is_read(mode, flags):
                self.note_file(os.fsdecode(path))
        elif event == "sqlite3.connect":
            path = arguments[0]
            if isinstance(path, (str, bytes, os.PathLike)):
                text = os.fsdecode(path)
                if text.startswith("file:"):
                    text = text.removeprefix("file:").partition("?")[0]
                if text and text != ":memory:":
                    self.note_file(text)
        elif event in {"os.listdir", "os.scandir"}:
            path = arguments[0]
            if isinstance(path, int):
                self.note_incomplete(f"{event} by file descriptor")
            elif path is None:
                self.note_listing(os.getcwd())
            elif isinstance(path, (str, bytes, os.PathLike)):
                self.note_listing(os.fsdecode(path))

    def note_imported_modules(self) -> None:
        """Record every imported module's source; one changed since the process started is unobservable."""
        with self.suspended():
            self._note_imported_modules()

    def _note_imported_modules(self) -> None:
        for module in list(sys.modules.values()):
            location = getattr(module, "__file__", None)
            if not isinstance(location, str):
                continue
            path = _source_of(Path(os.path.abspath(location)))
            if path in self.files or not self._admitted(path):
                continue
            try:
                modified = path.stat().st_mtime_ns
            except OSError:
                modified = None
            if modified is None or modified >= self.started_ns:
                self.note_incomplete(f"module {path} changed after the process started")
            self.note_file(str(path))

    def merge_journal(self, journal: Path) -> None:
        """Fold one worker's journal into this observation."""
        try:
            lines = journal.read_text(encoding="utf-8", errors="surrogateescape").splitlines()
        except OSError as error:
            self.note_incomplete(f"unreadable worker journal {journal.name}: {type(error).__name__}")
            return
        if not lines or lines[0].split("\t", 1)[0] != _BEGIN:
            self.note_incomplete(f"worker journal {journal.name} never began")
            return
        for line in lines[1:]:
            kind, _, rest = line.partition("\t")
            digest, _, location = rest.partition("\t")
            if kind == _FILE:
                self.files.setdefault(Path(location), digest)
            elif kind == _LISTING:
                self.listings.setdefault(Path(location), digest)
            elif kind == _INCOMPLETE:
                self.incomplete.append(f"worker: {location}")
            else:
                self.incomplete.append(f"worker journal {journal.name} has an unreadable line")

    def harvest(self, directory: Path) -> None:
        """Fold every worker journal written under ``directory``."""
        with self.suspended():
            try:
                journals = sorted(path for path in directory.iterdir() if path.suffix == _JOURNAL_SUFFIX)
            except OSError as error:
                self.note_incomplete(f"unreadable worker journal directory: {type(error).__name__}")
                return
            for journal in journals:
                self.merge_journal(journal)


_ACTIVE: Observation | None = None


def active_observation() -> Observation | None:
    """Return this process's observation, or ``None`` when it runs unobserved."""
    return _ACTIVE


def observe_process(root: Path) -> Observation:
    """Start observing this process. Call it before any product module is imported.

    An audit hook cannot be removed, so this is for an entry point that owns its
    process: the ``check`` command line and the docs profile worker.
    """
    global _ACTIVE
    if _ACTIVE is not None:
        return _ACTIVE
    observation = Observation(root, started_ns=time.time_ns())
    _ACTIVE = observation
    sys.addaudithook(observation.audit)
    return observation


@contextmanager
def unobserved() -> Generator[None]:
    """Run a block on this thread without recording its reads (no-op when the process is unobserved)."""
    if _ACTIVE is None:
        yield
        return
    with _ACTIVE.suspended():
        yield


def prepare_worker_journals(storage_root: Path) -> Path | None:
    """Prepare the journal directory and worker script for a sandbox, when this process is observed.

    Returns:
        The directory holding the worker script copy (``observed_worker.py``)
        and the journals its workers write, or ``None`` when unobserved.
    """
    from .observed_worker import CHECKOUT_ROOT_FILE

    if _ACTIVE is None:
        return None
    directory = storage_root.parent / JOURNAL_DIRECTORY_NAME
    directory.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).with_name(WORKER_SCRIPT_NAME)
    (directory / WORKER_SCRIPT_NAME).write_bytes(script.read_bytes())
    (directory / CHECKOUT_ROOT_FILE).write_text(str(_ACTIVE.root), encoding="utf-8")
    return directory


def observe_worker(root: Path, journals: Path) -> None:
    """Observe this docs profile worker, streaming what it reads into a journal under ``journals``."""
    observation = observe_process(root)
    journal = (journals / f"{os.getpid()}{_JOURNAL_SUFFIX}").open("a", encoding="utf-8", errors="surrogateescape")
    observation.attach_journal(journal)
