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

Existence and metadata probes (``os.stat``, ``os.path.exists`` and the
``pathlib`` predicates built on them) raise no audit event, so the observer
wraps those functions when it is installed: a probed path is recorded as its
digest, ``directory`` or ``absent``. A child process is covered only when it
journals itself: an observed docs worker, or a Python ``-m`` child of a checkout
module, which an observed process starts through a bootstrap
(``observed_child.py``) that installs this observer first. The parent expects
one journal per such child and treats a missing one as unobservable.

What the hook cannot see is reported, never guessed:

- a module imported before the hook whose file changed after the process
  started;
- a listing addressed by file descriptor;
- any other child process (``subprocess``, ``os.spawn*``, ``os.exec*``,
  ``os.system``, a native ``CreateProcess*``), or a native launch whose command
  line was not seen;
- an unreadable observed file, or two processes that read different bytes for
  the same file;
- a worker journal that never began, or that says it is incomplete.

Each makes the observation incomplete, and the verdict cache then keys the
sequence on the whole product source instead.
"""

from __future__ import annotations

import ast
import atexit
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Generator, Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Final, TextIO, cast

#: The directory, beside a sandbox's profile storage root, that collects worker journals.
JOURNAL_DIRECTORY_NAME: Final[str] = "docs-dependency-observations"
#: The observed worker script's name, in the checkout and as copied beside the journals.
WORKER_SCRIPT_NAME: Final[str] = "observed_worker.py"
#: The bootstrap an observed process starts its Python ``-m`` checkout children through.
CHILD_SCRIPT_NAME: Final[str] = "observed_child.py"
#: The file, beside the script copies, that names the checkout root.
CHECKOUT_ROOT_FILE: Final[str] = "checkout-root.txt"
_JOURNAL_SUFFIX: Final[str] = ".journal"
_BEGIN: Final[str] = "B"
_FILE: Final[str] = "F"
_LISTING: Final[str] = "D"
_INCOMPLETE: Final[str] = "X"
_EXPECTED: Final[str] = "E"
_CONSTRUCTOR: Final[str] = "__init__"
_BYTECODE_DIRECTORY: Final[str] = "__pycache__"
_ABSENT: Final[str] = "absent"
_DIRECTORY: Final[str] = "directory"
#: Audit events that start a child process. A Popen also raises the native
#: launch event it is built on; that one is consumed by the Popen's verdict.
_POPEN_EVENT: Final[str] = "subprocess.Popen"
_NATIVE_LAUNCH_EVENTS: Final[frozenset[str]] = frozenset({"_winapi.CreateProcess", "os.posix_spawn"})
_OTHER_SPAWN_EVENTS: Final[frozenset[str]] = frozenset(
    {"os.system", "os.spawn", "os.exec", "os.startfile", "os.fork", "os.forkpty"}
)
#: A ``ctypes`` launch names its entry point first and builds its command line
#: buffer next; a lookup with no command line seen afterwards stays unknown.
_NATIVE_SPAWN_PREFIX: Final[str] = "CreateProcess"
#: Checkout trees that hold environments, scratch, build output and caches, never verdict inputs.
STRUCTURAL_EXCLUSIONS: Final[tuple[str, ...]] = (".venv", ".tmp", "build", "node_modules", ".git", ".cache")


def _is_read(mode: object, flags: object) -> bool:
    """Whether an open can consume the file's existing bytes (``r``, ``r+``, ``a+``; not ``w``, ``x``, ``a``)."""
    if isinstance(mode, str):
        return "r" in mode or ("a" in mode and "+" in mode)
    if not isinstance(flags, int):
        return True
    return not (flags & os.O_WRONLY or flags & os.O_TRUNC or flags & os.O_EXCL)


def _source_of(path: Path) -> Path:
    """Map ``pkg/__pycache__/mod.cpython-313.pyc`` to the ``pkg/mod.py`` it was compiled from."""
    if path.parent.name != _BYTECODE_DIRECTORY or path.suffix != ".pyc":
        return path
    return path.parent.parent / f"{path.name.split('.', 1)[0]}.py"


def file_digest(path: Path) -> str:
    """Return the SHA-256 of ``path``'s bytes, ``directory`` for a directory, or ``absent``."""
    if path.is_dir():
        return _DIRECTORY
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


def _is_type_checking_guard(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def resolved_import_module(node: ast.ImportFrom, package: str) -> str:
    """Return the absolute module an ``ImportFrom`` names, resolving relative levels against ``package``."""
    if node.level:
        parts = package.split(".")
        base = ".".join(parts[: len(parts) - node.level + 1])
        return f"{base}.{node.module}" if node.module is not None and node.module != "" else base
    return node.module or ""


def imported_modules(tree: ast.Module, package: str) -> Iterator[str]:
    """Yield every dotted name a module may import at runtime, including lazy imports.

    Relative imports resolve against ``package``. ``from a import b`` yields both
    ``a`` and ``a.b`` because ``b`` may be a submodule; a name that is not a module
    simply resolves to no file. Imports guarded by ``TYPE_CHECKING`` never run.
    """
    pending: list[ast.AST] = list(tree.body)
    while pending:
        node = pending.pop()
        if isinstance(node, ast.If) and _is_type_checking_guard(node):
            pending.extend(node.orelse)
            continue
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolved_import_module(node, package)
            yield module
            yield from (f"{module}.{alias.name}" for alias in node.names)
        pending.extend(ast.iter_child_nodes(node))


def module_files(module: str, source_roots: Iterable[Path]) -> Iterator[Path]:
    """Yield the files importing ``module`` executes: each package ``__init__`` and the module, per source root."""
    parts = [part for part in module.split(".") if part]
    for source_root in source_roots:
        for end in range(1, len(parts) + 1):
            base = source_root.joinpath(*parts[:end])
            for candidate in (base / "__init__.py", base.with_suffix(".py")):
                if candidate.is_file():
                    yield candidate


def static_import_closure(
    starts: Iterable[Path],
    source_roots: tuple[Path, ...],
    *,
    admit: Callable[[Path], bool] = lambda _path: True,
) -> set[Path]:
    """Return ``starts`` and every module under ``source_roots`` they import, transitively, read statically."""
    pending = list(starts)
    seen: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in seen:
            continue
        seen.add(path)
        package = _package_of(path, source_roots)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module in imported_modules(tree, package):
            pending.extend(imported for imported in module_files(module, source_roots) if admit(imported))
    return seen


def _package_of(path: Path, source_roots: tuple[Path, ...]) -> str:
    for source_root in source_roots:
        if path.is_relative_to(source_root):
            parts = path.relative_to(source_root).parent.parts
            return ".".join(parts)
    return ""


class Observation:
    """The checkout files and listings one process consumed, each with its first-seen digest."""

    def __init__(self, root: Path, *, started_ns: int) -> None:
        self.root = root.resolve()
        self._excluded = tuple(self.root / name for name in STRUCTURAL_EXCLUSIONS)
        self.started_ns = started_ns
        self.files: dict[Path, str] = {}
        self.listings: dict[Path, str] = {}
        self.incomplete: list[str] = []
        #: Script copies whose processes journal themselves; a launch running one is covered.
        self.worker_scripts: set[str] = set()
        #: Where this process's instrumented children journal, while it has such a directory.
        self.journal_directory: Path | None = None
        #: The check process's own journal directory, for children it starts outside a sandbox.
        self.own_journals: Path | None = None
        #: Children started through the bootstrap: journal name to the directory it must
        #: begin in and the time it was launched.
        self.expected_children: dict[str, tuple[Path, int]] = {}
        self._begun: set[Path] = set()
        self._journal: TextIO | None = None
        self._journal_path: Path | None = None
        self._lock = threading.RLock()
        self._busy = threading.local()
        self._launches = threading.local()
        self._pending_native: dict[int, str] = {}
        given = Path(os.path.abspath(root))
        self._aliases = tuple(dict.fromkeys((self.root, given)))
        self._real_parents: dict[str, Path] = {}

    def _canonical(self, raw: str) -> Path | None:
        """Return ``raw`` rebased onto the resolved checkout root, or ``None`` when it lies outside it.

        A path reaching the checkout through a junction, ``subst`` drive or 8.3
        name is resolved by its directory once, so no alias of the root hides a read.
        """
        path = Path(os.path.abspath(raw))
        for alias in self._aliases:
            if path.is_relative_to(alias):
                return self.root / path.relative_to(alias)
        parent = str(path.parent)
        real = self._real_parents.get(parent)
        if real is None:
            real = Path(os.path.realpath(parent))
            self._real_parents[parent] = real
        candidate = real / path.name
        return candidate if candidate.is_relative_to(self.root) else None

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

    def attach_journal_path(self, journal: Path) -> None:
        """Like :meth:`attach_journal`, but reopen ``journal`` for each line, holding no descriptor in between.

        A contained child may audit its own open descriptors, so it keeps none.
        """
        with self._lock, self.suspended():
            self._journal_path = journal
            with journal.open("a", encoding="utf-8", errors="surrogateescape") as handle:
                handle.write(f"{_BEGIN}\t-\t{os.getpid()}\n")
            for path, digest in self.files.items():
                self._write(_FILE, digest, path)
            for directory, digest in self.listings.items():
                self._write(_LISTING, digest, directory)
            for reason in self.incomplete:
                self._write(_INCOMPLETE, "-", reason)

    def _write(self, kind: str, digest: str, path: Path | str) -> None:
        line = f"{kind}\t{digest}\t{path}\n"
        if self._journal is not None:
            self._journal.write(line)
            self._journal.flush()
        elif self._journal_path is not None:
            with self.suspended(), self._journal_path.open("a", encoding="utf-8", errors="surrogateescape") as handle:
                handle.write(line)

    def note_file(self, raw: str) -> None:
        canonical = self._canonical(raw)
        if canonical is None:
            return
        path = _source_of(canonical)
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
        directory = self._canonical(raw)
        if directory is None or directory in self.listings or not self._admitted(directory):
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
        """The audit hook: record reads, listings and launches, never re-entering itself."""
        if getattr(self._busy, "active", False):
            return
        with self.suspended():
            try:
                self._dispatch(event, arguments)
            except Exception as error:  # an observer fault must not change the observed program
                self.note_incomplete(f"observer fault on {event}: {type(error).__name__}")

    def probe(self, raw: object) -> None:
        """Record a path whose existence or metadata the observed program inspected."""
        if getattr(self._busy, "active", False) or not isinstance(raw, (str, bytes, os.PathLike)):
            return
        with self.suspended():
            try:
                self.note_file(os.fsdecode(cast("str | bytes | os.PathLike[str]", raw)))
            except Exception as error:  # an observer fault must not change the observed program
                self.note_incomplete(f"observer fault on a probe: {type(error).__name__}")

    def _launch(self, event: str, arguments: tuple[object, ...]) -> None:
        if event == _POPEN_EVENT:
            command = arguments[1]
            words = [command] if isinstance(command, (str, bytes)) else list(cast("Iterable[object]", command))
            self._judge_launch([os.fsdecode(word) for word in words if isinstance(word, (str, bytes, os.PathLike))])
            self._launches.covered = True
        elif event in _NATIVE_LAUNCH_EVENTS:
            if getattr(self._launches, "covered", False):
                self._launches.covered = False
                return
            self.note_incomplete(f"unjudged child process ({event})")
        else:
            self.note_incomplete(f"unobserved child process ({event})")

    def _judge_launch(self, words: list[str]) -> None:
        """Cover a launch whose process journals itself; any other child makes the observation incomplete."""
        line = " ".join(words)
        folded = line.casefold()
        if not any(script.casefold() in folded for script in self.worker_scripts):
            self.note_incomplete(f"unobserved child process {line[:200]}")

    def instrument_child(self, command: object) -> object:
        """Route a Python ``-m`` child of a checkout module through the observing bootstrap.

        Returns ``command`` unchanged when it is anything else, or when this
        process has no journal directory; the launch is then judged unobserved.
        """
        if self.journal_directory is None or not isinstance(command, (list, tuple)):
            return command
        words = [os.fsdecode(word) for word in command if isinstance(word, (str, bytes, os.PathLike))]
        if len(words) != len(command):
            return command
        with self.suspended():
            module = _python_module(words)
            if module is None or not any(True for _ in module_files(module, self._source_roots())):
                return command
            token = uuid.uuid4().hex
            index = words.index("-m")
            script = str(self.journal_directory / CHILD_SCRIPT_NAME)
            launched_ns = time.time_ns()
            with self._lock:
                self.expected_children[token] = (self.journal_directory, launched_ns)
                self._write(_EXPECTED, str(launched_ns), token)
            return [*words[:index], script, token, module, *words[index + 2 :]]

    def adopt_journal_directory(self, directory: Path) -> None:
        """Journal instrumented children in ``directory`` and recognise launches of its script copies."""
        with self.suspended():
            self.journal_directory = directory
            for name in (WORKER_SCRIPT_NAME, CHILD_SCRIPT_NAME):
                copy = directory / name
                self.worker_scripts.update({str(copy), str(copy.resolve())})

    def _source_roots(self) -> tuple[Path, ...]:
        roots: list[Path] = []
        for entry in sys.path:
            canonical = self._canonical(entry or os.getcwd())
            if canonical is not None and self._admitted(canonical) and canonical.is_dir() and canonical not in roots:
                roots.append(canonical)
        return tuple(roots)

    def _native_lookup(self, name: str) -> None:
        if name.startswith(_NATIVE_SPAWN_PREFIX):
            with self._lock:
                self._pending_native[threading.get_ident()] = name

    def _native_command(self, init: object) -> None:
        with self._lock:
            name = self._pending_native.pop(threading.get_ident(), None)
        if name is None:
            return
        if isinstance(init, str):
            self._judge_launch([init])
        else:
            self.note_incomplete(f"native {name} launch with an unseen command line")

    def settle_launches(self) -> None:
        """Mark the observation incomplete for a native launch whose command line was never seen."""
        with self._lock:
            pending = sorted(set(self._pending_native.values()))
            self._pending_native.clear()
        for name in pending:
            self.note_incomplete(f"native {name} launch with an unseen command line")

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
        elif event == _POPEN_EVENT or event in _NATIVE_LAUNCH_EVENTS or event in _OTHER_SPAWN_EVENTS:
            self._launch(event, arguments)
        elif event == "ctypes.dlsym" and len(arguments) > 1 and isinstance(arguments[1], str):
            self._native_lookup(arguments[1])
        elif event == "ctypes.create_unicode_buffer":
            self._native_command(arguments[0])

    def note_imported_modules(self) -> None:
        """Record every imported module's source; one changed since the process started is unobservable."""
        with self.suspended():
            self._note_imported_modules()
        if self.own_journals is not None:
            self.harvest(self.own_journals)
        self.settle_launches()

    def _note_imported_modules(self) -> None:
        for module in list(sys.modules.values()):
            location = getattr(module, "__file__", None)
            if not isinstance(location, str):
                continue
            canonical = self._canonical(location)
            if canonical is None:
                continue
            path = _source_of(canonical)
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
        self._begun.add(journal)
        for line in lines[1:]:
            kind, _, rest = line.partition("\t")
            digest, _, location = rest.partition("\t")
            if kind == _FILE:
                self._merge_entry(self.files, Path(location), digest)
            elif kind == _LISTING:
                self._merge_entry(self.listings, Path(location), digest)
            elif kind == _INCOMPLETE:
                self.incomplete.append(f"worker: {location}")
            elif kind == _EXPECTED and digest.isdecimal():
                self.expected_children.setdefault(location, (journal.parent, int(digest)))
            else:
                self.incomplete.append(f"worker journal {journal.name} has an unreadable line")

    def _merge_entry(self, entries: dict[Path, str], path: Path, digest: str) -> None:
        """Keep the first digest; two processes that read different bytes make the run unobservable."""
        recorded = entries.setdefault(path, digest)
        if recorded != digest:
            self.note_incomplete(f"{path} changed between the processes that read it")

    def harvest(self, directory: Path, *, settled_ns: int | None = None) -> None:
        """Fold every worker journal written under ``directory``.

        A child that left no journal makes the observation incomplete, unless it
        was launched at or after ``settled_ns``: the moment the sequence's output
        was complete, after which a child (a shutdown wrap the runtime kills with
        its worker) cannot have shaped what the check compares.
        """
        with self.suspended():
            try:
                journals = sorted(path for path in directory.iterdir() if path.suffix == _JOURNAL_SUFFIX)
            except OSError as error:
                self.note_incomplete(f"unreadable worker journal directory: {type(error).__name__}")
                return
            for journal in journals:
                self.merge_journal(journal)
            for token, (expected, launched_ns) in sorted(self.expected_children.items()):
                if expected != directory or directory / f"{token}{_JOURNAL_SUFFIX}" in self._begun:
                    continue
                if settled_ns is None or launched_ns < settled_ns:
                    self.note_incomplete(f"instrumented child {token} left no journal")
            if self.journal_directory == directory and directory != self.own_journals:
                self.journal_directory = self.own_journals


def _python_module(words: list[str]) -> str | None:
    """Return the module a ``python [options] -m module`` command line runs, or ``None``."""
    if not words:
        return None
    executable = Path(words[0]).name.casefold()
    known = {Path(path).name.casefold() for path in (sys.executable, getattr(sys, "_base_executable", "")) if path}
    if not (executable.startswith("python") or executable in known):
        return None
    for index, word in enumerate(words[1:-1], start=1):
        if word == "-m":
            return words[index + 1]
        if not word.startswith("-") or word == "-c":
            return None
    return None


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
    _wrap_probes(observation)
    _wrap_child_launches(observation)
    return observation


def _wrap_child_launches(observation: Observation) -> None:
    """Start Python ``-m`` checkout children through the observing bootstrap while journals are collected."""
    original: Callable[..., None] = getattr(subprocess.Popen, _CONSTRUCTOR)

    def launch(self: object, args: object, *arguments: object, **keywords: object) -> None:
        original(self, observation.instrument_child(args), *arguments, **keywords)

    setattr(subprocess.Popen, _CONSTRUCTOR, launch)


def _wrap_probes(observation: Observation) -> None:
    """Route the existence and metadata probes, which raise no audit event, through the observation."""

    def wrapped(function: Callable[..., object]) -> Callable[..., object]:
        def probe(path: object, *arguments: object, **keywords: object) -> object:
            observation.probe(path)
            return function(path, *arguments, **keywords)

        probe.__name__ = getattr(function, "__name__", "probe")
        probe.__doc__ = function.__doc__
        return probe

    for name in ("stat", "lstat", "access"):
        setattr(os, name, wrapped(getattr(os, name)))
    for name in ("exists", "lexists", "isfile", "isdir", "islink", "getsize", "getmtime"):
        setattr(os.path, name, wrapped(getattr(os.path, name)))


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
    if _ACTIVE is None:
        return None
    directory = storage_root.parent / JOURNAL_DIRECTORY_NAME
    _populate_journal_directory(_ACTIVE, directory)
    return directory


def _populate_journal_directory(observation: Observation, directory: Path) -> None:
    """Copy the observing scripts and the checkout pointer into ``directory`` and journal children there."""
    with observation.suspended():
        directory.mkdir(parents=True, exist_ok=True)
        for name in (WORKER_SCRIPT_NAME, CHILD_SCRIPT_NAME):
            (directory / name).write_bytes(Path(__file__).with_name(name).read_bytes())
        (directory / CHECKOUT_ROOT_FILE).write_text(str(observation.root), encoding="utf-8")
    observation.adopt_journal_directory(directory)


def observe_check(root: Path) -> Observation:
    """Observe the ``check`` process, with a journal directory of its own for children it starts itself.

    The directory sits under the checkout's ``.tmp`` and is removed when the process exits.
    """
    observation = observe_process(root)
    if observation.own_journals is None:
        scratch = observation.root / ".tmp"
        with observation.suspended():
            scratch.mkdir(exist_ok=True)
            directory = Path(tempfile.mkdtemp(prefix="docs-observed-", dir=scratch))
        atexit.register(shutil.rmtree, directory, ignore_errors=True)
        observation.own_journals = directory
        _populate_journal_directory(observation, directory)
    return observation


def observe_worker(root: Path, journals: Path) -> None:
    """Observe this docs profile worker, streaming what it reads into a journal under ``journals``."""
    observation = observe_process(root)
    observation.adopt_journal_directory(journals)
    journal = (journals / f"{os.getpid()}{_JOURNAL_SUFFIX}").open("a", encoding="utf-8", errors="surrogateescape")
    observation.attach_journal(journal)


def observe_child(root: Path, journals: Path, token: str) -> None:
    """Observe an instrumented child, journalling under ``journals`` by the name its parent expects."""
    observation = observe_process(root)
    observation.adopt_journal_directory(journals)
    observation.attach_journal_path(journals / f"{token}{_JOURNAL_SUFFIX}")
