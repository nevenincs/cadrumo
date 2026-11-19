"""Observe the checkout files and directory listings an observed process and its children actually read.

A tool runs a command in the checking interpreter and may start child
interpreters (profile workers, Python ``-m`` modules). Each process that runs
under observation installs a Python audit hook before it imports any product module. The hook
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
journals itself: an observed worker script, or a Python ``-m`` child of a
checkout module, which an observed process starts through a bootstrap
(``observed_child.py``) that installs this observer first. A child killed
before that leaves an empty journal or none, having run no product code.

A run can instead hand its whole process tree an inherited bootstrap
(:func:`prepare_inherited_journals`): every Python process that keeps the run's
environment observes itself as it starts, whoever launches it. Such a process
covers a Python child that keeps that environment and starts without ``-I``,
``-E`` or ``-S``, and a ``-m`` checkout child, which it starts through the
journalling child bootstrap; any other child it starts is unobserved. A run in which no
process journalled at all was not observed.

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

A directory the run itself creates (``os.mkdir``, so ``tempfile`` scratch as
well) is not an input: reads under it are dropped, and the listing of the
directory that holds it is taken again once the run is done, when the scratch
is normally gone.

Each makes the observation incomplete, and the consumer then keys on the whole
product source instead.
"""

from __future__ import annotations

import ast
import atexit
import hashlib
import os
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable, Generator, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final, TextIO, cast
from urllib.parse import unquote, urlsplit

#: The bootstrap an observed process starts its Python ``-m`` checkout children through.
CHILD_SCRIPT_NAME: Final[str] = "observed_child.py"
#: The file, beside the script copies, that names the checkout root.
CHECKOUT_ROOT_FILE: Final[str] = "checkout-root.txt"
#: The suffix of every journal file an observed process writes.
JOURNAL_SUFFIX: Final[str] = ".journal"
_BEGIN: Final[str] = "B"
_FILE: Final[str] = "F"
_LISTING: Final[str] = "D"
_INCOMPLETE: Final[str] = "X"
_CREATED: Final[str] = "C"
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
#: Names an inherited run's journal directory to every process below it; see :func:`prepare_inherited_journals`.
INHERITED_JOURNALS_VARIABLE: Final[str] = "CADRUMO_OBSERVED_JOURNALS"
#: The directory, inside an inherited run's journals, that is put first on ``PYTHONPATH``.
INHERITED_SITE_DIRECTORY: Final[str] = "site"
#: Names the observer's checkout and the observed checkout, one per line, for the inherited bootstrap.
INHERITED_ROOTS_FILE: Final[str] = "observer-roots.txt"
_INHERITED_BOOTSTRAP: Final[str] = "inherited_bootstrap.py"
_SITE_HOOK: Final[str] = "sitecustomize.py"
_PYTHON_PATH: Final[str] = "PYTHONPATH"
#: Interpreter options under which a child would not import the inherited bootstrap.
_ISOLATING_OPTIONS: Final[frozenset[str]] = frozenset("IES")

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
        """Observe reads under the checkout ``root`` made by a process started at ``started_ns``."""
        self.root = root.resolve()
        self._excluded = tuple(self.root / name for name in STRUCTURAL_EXCLUSIONS)
        self.started_ns = started_ns
        self.files: dict[Path, str] = {}
        self.listings: dict[Path, str] = {}
        self.incomplete: list[str] = []
        #: Directories the run created; nothing under them was an input.
        self.created: set[Path] = set()
        #: Script copies whose processes journal themselves; a launch running one is covered.
        self.worker_scripts: set[str] = set()
        #: Where this process's instrumented children journal, while it has such a directory.
        self.journal_directory: Path | None = None
        #: The check process's own journal directory, for children it starts outside a sandbox.
        self.own_journals: Path | None = None
        self._journal: TextIO | None = None
        self._journal_path: Path | None = None
        self._lock = threading.RLock()
        self._busy = threading.local()
        self._launches = threading.local()
        self._pending_native: dict[int, str] = {}
        #: An inherited run's journal directory, when this process observes itself as part of one.
        self.inherited_journals: Path | None = None
        given = Path(os.path.abspath(root))
        self._aliases = tuple(dict.fromkeys((self.root, given)))
        self._real_parents: dict[str, Path] = {}
        self._outside_seen: set[Path] = set()
        self._outside_allowed: list[Path] = [
            Path(os.path.realpath(location))
            for location in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix, tempfile.gettempdir()}
            if location
        ]

    def allow_outside(self, directory: Path) -> None:
        """Admit reads under ``directory``, outside the checkout, as inputs the verdict key already carries."""
        with self._lock:
            self._outside_allowed.append(Path(os.path.realpath(directory)))

    def _external(self, raw: str) -> Path | None:
        """Judge a read outside the checkout: return it to record, or ``None`` to skip it.

        Product source there (a ``cadrumo`` package, or Python source outside
        the interpreter's own trees) means another checkout's code ran, so the
        observation becomes incomplete. The explicit allowlist (the
        interpreter's prefixes, any ``site-packages``, the temporary directory,
        the null device and :meth:`allow_outside` directories) holds what the
        key already carries or what cannot shape a verdict, and is skipped.
        Anything else is recorded by its absolute path, like a checkout read.
        """
        path = Path(os.path.abspath(raw))
        if _is_foreign_source(path, self._outside_allowed):
            with self._lock:
                seen = path in self._outside_seen
                self._outside_seen.add(path)
            if not seen:
                self.note_incomplete(f"source read outside the checkout: {path}")
            return None
        if _allowed_outside(path, self._outside_allowed):
            return None
        return path

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
            for directory in self.created:
                self._write(_CREATED, "-", directory)
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
            for directory in self.created:
                self._write(_CREATED, "-", directory)
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
        """Record the file ``raw`` names, and the listing that would reveal a new sibling, if it is a checkout input."""
        canonical = self._canonical(raw)
        if canonical is None:
            external = self._external(raw)
            if external is not None:
                self._record_file(external)
            return
        path = _source_of(canonical)
        if path in self.files or not self._admitted(path):
            return
        self._record_file(path)
        if path != self.root:
            # The listing that would reveal a new sibling; the checkout's own
            # parent is not an input (a new worktree beside it changes nothing).
            self.note_listing(str(path.parent))

    def _record_file(self, path: Path) -> None:
        if path in self.files:
            return
        digest = file_digest(path)
        with self._lock:
            if path in self.files:
                return
            self.files[path] = digest
            self._write(_FILE, digest, path)

    def note_listing(self, raw: str) -> None:
        """Record the listing of the directory ``raw`` names, when it is a checkout input."""
        canonical = self._canonical(raw)
        if canonical is None:
            directory = self._external(raw)
            if directory is None:
                return
        elif not self._admitted(canonical):
            return
        else:
            directory = canonical
        if directory in self.listings:
            return
        digest = listing_digest(directory)
        with self._lock:
            if directory in self.listings:
                return
            self.listings[directory] = digest
            self._write(_LISTING, digest, directory)

    def note_incomplete(self, reason: str) -> None:
        """Mark the observation incomplete for ``reason``, journalling it."""
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
            decoded = [os.fsdecode(word) for word in words if isinstance(word, (str, bytes, os.PathLike))]
            if self.inherited_journals is not None:
                if isinstance(command, (str, bytes)):
                    decoded = _command_line_words(decoded[0]) if decoded else decoded
                self._judge_inherited_launch(arguments[0], decoded, arguments[3] if len(arguments) > 3 else None)
            else:
                self._judge_launch(decoded)
            self._launches.covered = True
        elif event in _NATIVE_LAUNCH_EVENTS:
            if getattr(self._launches, "covered", False):
                self._launches.covered = False
                return
            self.note_incomplete(f"unjudged child process ({event})")
        else:
            self.note_incomplete(f"unobserved child process ({event})")

    def _judge_inherited_launch(self, executable: object, words: list[str], environment: object) -> None:
        """Cover a Python child that keeps the inherited bootstrap; any other child makes the run incomplete."""
        line = " ".join(words)
        folded = line.casefold()
        if any(script.casefold() in folded for script in self.worker_scripts):
            return
        program = os.fsdecode(executable) if isinstance(executable, (str, bytes, os.PathLike)) else ""
        program = program or (words[0] if words else "")
        if not _is_python(program):
            self.note_incomplete(f"unobserved child process {line[:200]}")
        elif _isolating(words):
            self.note_incomplete(f"child process isolated from the inherited observer {line[:200]}")
        elif not self._keeps_inherited(os.environ if environment is None else environment):
            self.note_incomplete(f"child process without the inherited observer's environment {line[:200]}")

    def _keeps_inherited(self, environment: object) -> bool:
        journals = self.inherited_journals
        if journals is None or not isinstance(environment, Mapping):
            return False
        entries = {os.fsdecode(name): value for name, value in environment.items() if isinstance(name, (str, bytes))}
        named, path = entries.get(INHERITED_JOURNALS_VARIABLE), entries.get(_PYTHON_PATH)
        if not isinstance(named, (str, bytes)) or not isinstance(path, (str, bytes)):
            return False
        site = journals / INHERITED_SITE_DIRECTORY
        return _same_path(os.fsdecode(named), journals) and any(
            _same_path(part, site) for part in os.fsdecode(path).split(os.pathsep) if part
        )

    def end_launch(self) -> None:
        """Forget a judged Popen once it returns; a POSIX Popen raises no native event to consume it."""
        self._launches.covered = False

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
            return [*words[:index], script, token, module, *words[index + 2 :]]

    def adopt_journal_directory(self, directory: Path, script_names: Iterable[str] = (CHILD_SCRIPT_NAME,)) -> None:
        """Journal instrumented children in ``directory`` and recognise launches of its ``script_names`` copies."""
        with self.suspended():
            self.journal_directory = directory
            for name in script_names:
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
                    text = _uri_path(text)
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
        elif event == "os.mkdir":
            path = arguments[0]
            if isinstance(path, (str, bytes, os.PathLike)):
                self.note_created(os.fsdecode(path))
        elif event == _POPEN_EVENT or event in _NATIVE_LAUNCH_EVENTS or event in _OTHER_SPAWN_EVENTS:
            self._launch(event, arguments)
        elif event == "ctypes.dlsym" and len(arguments) > 1 and isinstance(arguments[1], str):
            self._native_lookup(arguments[1])
        elif event == "ctypes.create_unicode_buffer":
            self._native_command(arguments[0])

    def note_created(self, raw: str) -> None:
        """Record a directory this run is about to create; what is under it was written by the run, never read.

        The hook runs before the creation, so a path that already exists is not recorded.
        """
        canonical = self._canonical(raw)
        if canonical is None or not self._admitted(canonical) or os.path.lexists(canonical):
            return
        with self._lock:
            if canonical in self.created:
                return
            self.created.add(canonical)
            self._write(_CREATED, "-", canonical)

    def _within_created(self, path: Path) -> bool:
        return any(path.is_relative_to(directory) for directory in self.created)

    def settle_created(self) -> None:
        """Drop reads under directories the run created, and key their parents' listings on their state now.

        A run's own scratch is not an input. The directory that holds it lists that scratch only while the run
        lasts, so its listing is read again once the run's processes are done.
        """
        with self._lock, self.suspended():
            if not self.created:
                return
            for path in [path for path in self.files if self._within_created(path)]:
                del self.files[path]
            for path in [path for path in self.listings if self._within_created(path)]:
                del self.listings[path]
            for directory in self.created:
                parent = directory.parent
                if parent in self.listings and not self._within_created(parent):
                    self.listings[parent] = listing_digest(parent)

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
                self._external(location)
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
        """Fold one worker's journal into this observation.

        An empty journal belongs to a process killed before its observer
        started; it had imported no product module and read nothing that could
        shape the verdict (the observer writes its first line before the
        observed program runs), so it adds nothing. A non-empty journal that
        does not begin with that line is unreadable, and so incomplete.
        """
        try:
            lines = journal.read_text(encoding="utf-8", errors="surrogateescape").splitlines()
        except OSError as error:
            self.note_incomplete(f"unreadable worker journal {journal.name}: {type(error).__name__}")
            return
        if not lines:
            return
        if lines[0].split("\t", 1)[0] != _BEGIN:
            self.note_incomplete(f"worker journal {journal.name} never began")
            return
        for line in lines[1:]:
            kind, _, rest = line.partition("\t")
            digest, _, location = rest.partition("\t")
            if kind == _FILE:
                self._merge_entry(self.files, Path(location), digest)
            elif kind == _LISTING:
                self._merge_entry(self.listings, Path(location), digest)
            elif kind == _CREATED:
                self.created.add(Path(location))
            elif kind == _INCOMPLETE:
                self.incomplete.append(f"worker: {location}")
            else:
                self.incomplete.append(f"worker journal {journal.name} has an unreadable line")

    def _merge_entry(self, entries: dict[Path, str], path: Path, digest: str) -> None:
        """Keep the first digest; two processes that read different bytes make the run unobservable.

        Entries under a directory the run created, and the listing of the directory holding one, are settled by
        :meth:`settle_created` instead.
        """
        recorded = entries.setdefault(path, digest)
        if recorded != digest and not self._within_created(path) and not self._holds_created(path):
            self.note_incomplete(f"{path} changed between the processes that read it")

    def _holds_created(self, path: Path) -> bool:
        return any(directory.parent == path for directory in self.created)

    def _collect_created(self, journals: Sequence[Path]) -> None:
        """Learn every directory any process of the run created before any journal's reads are merged."""
        for journal in journals:
            try:
                lines = journal.read_text(encoding="utf-8", errors="surrogateescape").splitlines()
            except OSError:
                continue  # merge_journal reports it
            for line in lines[1:]:
                kind, _, rest = line.partition("\t")
                if kind == _CREATED:
                    self.created.add(Path(rest.partition("\t")[2]))

    def harvest(self, directory: Path) -> None:
        """Fold every worker journal written under ``directory``.

        A child that left no journal was killed before its bootstrap installed
        the observer, so it ran no product code (see :meth:`merge_journal`).
        """
        with self.suspended():
            try:
                journals = sorted(path for path in directory.iterdir() if path.suffix == JOURNAL_SUFFIX)
            except OSError as error:
                self.note_incomplete(f"unreadable worker journal directory: {type(error).__name__}")
                return
            self._collect_created(journals)
            for journal in journals:
                self.merge_journal(journal)
            self.settle_created()
            if self.journal_directory == directory and directory != self.own_journals:
                self.journal_directory = self.own_journals


#: Product package names; one of these outside the checkout is always another checkout's code.
_PRODUCT_PACKAGE_PREFIX: Final[str] = "cadrumo"
_SITE_PACKAGES: Final[str] = "site-packages"
_SOURCE_SUFFIXES: Final[frozenset[str]] = frozenset({".py", ".pyc", ".pyd", ".so", ".pth"})


def _uri_path(uri: str) -> str:
    """Return the filesystem path a SQLite ``file:`` URI names."""
    location = unquote(urlsplit(uri).path)
    if os.name == "nt" and location[:1] == "/" and location[2:3] == ":":
        location = location[1:]
    return location


def _is_foreign_source(path: Path, allowed: Iterable[Path]) -> bool:
    """Whether ``path`` is Python source of another checkout: product code, or source outside the allowed trees."""
    if path.suffix.casefold() not in _SOURCE_SUFFIXES:
        return False
    parts = [part.casefold() for part in path.parts]
    if _SITE_PACKAGES in parts:
        # An installed product (a wheel, or an editable finder or ``.pth`` naming
        # another checkout) is foreign; the directories above an environment are not.
        installed = parts[parts.index(_SITE_PACKAGES) + 1 :]
        return any(_PRODUCT_PACKAGE_PREFIX in part for part in installed)
    if not _allowed_outside(path, allowed):
        return True
    # Below the allowlisted directory that holds it, a product package is still another checkout's code.
    real = Path(os.path.realpath(path))
    for directory in allowed:
        for candidate in (path, real):
            if candidate.is_relative_to(directory):
                inner = candidate.relative_to(directory).parts
                if any(part.casefold().startswith(_PRODUCT_PACKAGE_PREFIX) for part in inner):
                    return True
    return False


def _allowed_outside(path: Path, allowed: Iterable[Path]) -> bool:
    """Whether ``path``, outside the checkout, is on the explicit allowlist of reads that cannot change a verdict."""
    if os.path.normcase(str(path)) == os.path.normcase(os.path.abspath(os.devnull)):
        return True
    if _SITE_PACKAGES in (part.casefold() for part in path.parts):
        return True
    real = Path(os.path.realpath(path))
    return any(real.is_relative_to(directory) or path.is_relative_to(directory) for directory in allowed)


def _same_path(raw: str, path: Path) -> bool:
    return os.path.normcase(os.path.realpath(raw)) == os.path.normcase(os.path.realpath(path))


def _command_line_words(line: str) -> list[str]:
    """Split a command line into its words.

    Windows hands the audit event the command line ``subprocess`` built, one string, not the argument list.
    """
    try:
        words = shlex.split(line, posix=os.name != "nt")
    except ValueError:
        return [line]
    return [word[1:-1] if len(word) > 1 and word[0] == word[-1] == '"' else word for word in words] or [line]


def _is_python(program: str) -> bool:
    name = Path(program).name.casefold()
    known = {Path(path).name.casefold() for path in (sys.executable, getattr(sys, "_base_executable", "")) if path}
    return name.startswith("python") or name in known


def _isolating(words: list[str]) -> bool:
    """Whether a ``python`` command line's options stop it importing the inherited bootstrap."""
    takes_value = False
    for word in words[1:]:
        if takes_value:
            takes_value = False
            continue
        if word == "-" or not word.startswith("-"):
            return False
        if word.startswith("--"):
            continue
        for index, option in enumerate(word[1:], start=1):
            if option in _ISOLATING_OPTIONS:
                return True
            if option in "cm":
                return False
            if option in "XW":
                # The value is the rest of this word, or the next word.
                takes_value = index == len(word) - 1
                break
    return False


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
        try:
            original(self, observation.instrument_child(args), *arguments, **keywords)
        finally:
            observation.end_launch()

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


def populate_journal_directory(observation: Observation, directory: Path, scripts: Mapping[str, Path]) -> None:
    """Copy each script in ``scripts`` (copy name to source file) and the checkout pointer into ``directory``.

    The observation then journals instrumented children there and recognises
    launches of the copies.
    """
    with observation.suspended():
        directory.mkdir(parents=True, exist_ok=True)
        for name, source in scripts.items():
            (directory / name).write_bytes(source.read_bytes())
        (directory / CHECKOUT_ROOT_FILE).write_text(str(observation.root), encoding="utf-8")
    observation.adopt_journal_directory(directory, scripts)


def observe_child(root: Path, journals: Path, token: str) -> None:
    """Observe an instrumented child, journalling under ``journals`` by the token its parent gave it.

    Every script copy in ``journals`` is a journalling launch for this child too.
    """
    observation = observe_process(root)
    with observation.suspended():
        copies = sorted(path.name for path in journals.glob("*.py"))
    observation.adopt_journal_directory(journals, {CHILD_SCRIPT_NAME, *copies})
    observation.attach_journal_path(journals / f"{token}{JOURNAL_SUFFIX}")


@dataclass(frozen=True, slots=True)
class InheritedJournals:
    """An inherited run's journal directory and the environment that makes its processes observe themselves."""

    directory: Path

    def environment(self, environment: Mapping[str, str]) -> dict[str, str]:
        """``environment`` naming this directory, with its bootstrap first on ``PYTHONPATH``."""
        result = dict(environment)
        result[INHERITED_JOURNALS_VARIABLE] = str(self.directory)
        parts = [str(self.directory / INHERITED_SITE_DIRECTORY), *result.get(_PYTHON_PATH, "").split(os.pathsep)]
        result[_PYTHON_PATH] = os.pathsep.join(dict.fromkeys(part for part in parts if part))
        return result


def prepare_inherited_journals(directory: Path, *, observed_root: Path, tooling_root: Path) -> InheritedJournals:
    """Prepare ``directory`` so every Python process given its environment observes reads under ``observed_root``.

    ``tooling_root`` is the checkout this observer is imported from; it is the observed checkout itself except
    when a tool observes another tree.
    """
    directory = directory.resolve()
    site = directory / INHERITED_SITE_DIRECTORY
    site.mkdir(parents=True, exist_ok=True)
    (site / _SITE_HOOK).write_bytes(Path(__file__).with_name(_INHERITED_BOOTSTRAP).read_bytes())
    roots = f"{tooling_root.resolve()}\n{observed_root.resolve()}\n"
    (directory / INHERITED_ROOTS_FILE).write_text(roots, encoding="utf-8")
    # A ``-m`` checkout child that skips site start-up (``-S``) is started through this bootstrap instead.
    (directory / CHILD_SCRIPT_NAME).write_bytes(Path(__file__).with_name(CHILD_SCRIPT_NAME).read_bytes())
    (directory / CHECKOUT_ROOT_FILE).write_text(str(observed_root.resolve()), encoding="utf-8")
    return InheritedJournals(directory)


def allow_observer_outside(observation: Observation, journals: Path) -> None:
    """Admit the journal directory and this observer, when imported from another checkout, as non-reads."""
    package = Path(__file__).resolve().parent
    for location in (journals, package, package.parent / "__init__.py"):
        observation.allow_outside(location)


def observe_inherited(root: Path, journals: Path) -> Observation:
    """Observe this process as part of an inherited run, journalling under ``journals`` until it exits."""
    observation = observe_process(root)
    allow_observer_outside(observation, journals)
    observation.inherited_journals = journals
    # A Python ``-m`` checkout child is started through the journalling child bootstrap, which covers it even when
    # its options skip the inherited one.
    observation.adopt_journal_directory(journals, (CHILD_SCRIPT_NAME,))
    observation.attach_journal_path(journals / f"{uuid.uuid4().hex}{JOURNAL_SUFFIX}")
    atexit.register(observation.note_imported_modules)
    return observation


def harvest_inherited(journals: InheritedJournals, root: Path) -> Observation:
    """Fold every journal of an inherited run over ``root``; a run in which no process began was not observed."""
    observation = Observation(root, started_ns=time.time_ns())
    began = any(path.suffix == JOURNAL_SUFFIX and path.stat().st_size > 0 for path in journals.directory.iterdir())
    if not began:
        observation.note_incomplete("no process of the run was observed")
    observation.harvest(journals.directory)
    return observation
