"""Reuse a clean cli-sequence verdict, sequence by sequence, when nothing it depends on changed.

Each documented sequence executes against the real CLI and compares its
transcript with its committed golden. Its verdict is a pure function of three
parts:

- the corpus inputs every sequence shares: the interpreter and platform, the
  environment variables that configure the product, the published registry
  authority with the tooling and product modules that compile it, the gate
  engine and every ``dev`` module it imports, the locked dependencies, and the
  shared seeds and fixtures under ``docs/_sequences``;
- the sequence's own inputs: its page and id, the parsed sequence the runner
  executes (directive options merged with the private contract), the private
  contract's bytes and the committed golden's bytes;
- the product it reached: every checkout file and directory listing its
  processes were observed to read (:mod:`dev.docs.sequences.dependency_observation`),
  each with the digest it had when it was read. When that observation is
  unavailable, incomplete (product source read from outside the checkout
  makes it so) or missing the product package itself, the whole product source (the CLI, its runtime, its client
  and its registry data) stands in for it.

The first two parts form the record's key, enumerated from the filesystem and
from the engine's static import graph, so any change to a shared input
re-executes every sequence and a change to one sequence's own inputs
re-executes only it. The record holds the third part, and a recorded verdict
is reused only while every file and listing in it still has its recorded
digest, so a product edit re-executes exactly the sequences that read it. The
published authority enters as its logical generation together with the
registry tooling that compiles it, because two publications of one source
differ in database bytes.

Only a clean sequence is recorded, immediately after it passes, so an
interrupted run keeps the verdicts it completed. A divergence is never
recorded, so a record can cost a re-run but can never turn a failing sequence
green. A record is refused when any input changed while the sequence ran, and
every reuse reports which recorded verdict stood in for execution.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, Protocol

from cadrumo.core.directory_scan import DirectoryEntryKind, scan_directory
from dev.cache_root import dev_cache_dir
from dev.first_party_source import PRODUCT_SOURCE_ROOTS
from dev.locales.write_guard import LOCK_FILENAME
from dev.paths import REPO_ROOT

from .authority_currency import require_current_authority
from .contracts import sequence_contract_path
from .dependency_observation import Observation, file_digest, listing_digest, static_import_closure, unobserved
from .errors import SequenceEngineError
from .golden_store import golden_path
from .schema import ParsedSequence

#: Set to bypass reuse and always execute every sequence; passing sequences are still recorded.
FORCE_ENV: Final[str] = "CADRUMO_DOCS_FORCE_SEQUENCE_CHECK"
_CACHE_NAME: Final[str] = "docs-sequence-verdicts"
_RECORD_FORMAT: Final[str] = "cli-sequence-verdict/5"
_OBSERVED: Final[str] = "observed"
_CLOSURE: Final[str] = "closure"
_PRUNED: Final[tuple[str, ...]] = ("__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache")
#: The engine's entry points; every ``dev`` module they import, transitively, is a verdict input.
ENGINE_ROOTS: Final[tuple[str, ...]] = ("dev/docs/sequences", "dev/docs/sequence_build_gate.py", "dev/docs/build.py")
#: Registry tooling reaches the verdict only through the published authority it
#: compiles. The key carries the authority's logical generation and hashes this
#: whole tree beside it, so the engine's import walk need not follow it.
_AUTHORITY_TOOLING: Final[str] = "dev/registry/"
#: The publication entry point; the product modules it imports shape the compiled
#: authority bytes without changing its logical generation, so they are corpus inputs.
_AUTHORITY_COMPILER: Final[str] = "dev/registry/pipeline/authority_publication.py"
#: Every sequence imports this, so an observation without it never saw the product.
OBSERVATION_SENTINEL: Final[str] = "src/cadrumo/__init__.py"
#: Environment variables that configure the product or its rendering enter every key.
#: Those that only steer this tooling or its test runner do not.
_ENVIRONMENT_PREFIX: Final[str] = "CADRUMO_"
_ENVIRONMENT_NAMES: Final[frozenset[str]] = frozenset(
    {
        "LANG",
        "LANGUAGE",
        "LC_ALL",
        "LC_MESSAGES",
        "TZ",
        "PYTHONHASHSEED",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTHONPATH",
        "COLUMNS",
        "NO_COLOR",
        "FORCE_COLOR",
        "TERM",
    }
)
_TOOLING_ENVIRONMENT: Final[frozenset[str]] = frozenset(
    {"CADRUMO_DEV_CACHE_ROOT", "CADRUMO_DOCS_FORCE_SEQUENCE_CHECK", "CADRUMO_PYTEST_WORKERS"}
)
#: Under ``docs/_sequences`` these subtrees hold per-sequence inputs, keyed
#: sequence by sequence; everything else there (seeds, fixtures) is shared.
_CONTRACTS_DIRECTORY: Final[str] = "contracts"
_GOLDEN_SUFFIX: Final[str] = ".json"


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...


class KeyedSequence(Protocol):
    """The discovered-sequence shape a verdict is keyed on."""

    @property
    def page(self) -> str: ...

    @property
    def sequence_id(self) -> str: ...

    @property
    def sequence(self) -> ParsedSequence: ...


@dataclass
class _InputTrace:
    """Every file and tree one key read, so a later change can be detected and declared."""

    files: set[Path] = field(default_factory=set)
    directories: set[Path] = field(default_factory=set)
    absent: set[Path] = field(default_factory=set)
    trees: list[tuple[Path, tuple[str, ...]]] = field(default_factory=list)

    def hash_file(self, digest: _Digest, path: Path, *, label: str) -> None:
        self.files.add(path)
        digest.update(f"{label}\n".encode())
        with path.open("rb") as handle:
            digest.update(hashlib.file_digest(handle, "sha256").digest())

    def hash_tree(
        self,
        digest: _Digest,
        root: Path,
        *,
        label: str,
        skip: tuple[str, ...] = (),
    ) -> None:
        """Hash every file under ``root`` (or ``root`` itself), skipping the top-level ``skip`` names."""
        if not root.exists():
            self.absent.add(root)
            digest.update(f"absent:{label}\n".encode())
            return
        if root.is_file():
            self.hash_file(digest, root, label=f"{label}/{root.name}")
            return
        self.trees.append((root, skip))
        self.directories.add(root)
        for path in _tree_files(root, skip):
            relative = path.relative_to(root)
            self.directories.update(path.parents[: len(relative.parts) - 1])
            self.hash_file(digest, path, label=f"{label}/{relative.as_posix()}")

    def snapshot(self) -> dict[Path, tuple[int, int] | None]:
        """Return each traced file's size and modification time; ``None`` for an absent path."""
        return {path: _stat(path) for path in (*self.files, *self.absent)}

    def current_files(self) -> set[Path]:
        """Re-enumerate the traced trees, so an added or removed file is seen as a change."""
        files = {path for path in self.files if not any(path.is_relative_to(root) for root, _ in self.trees)}
        for root, skip in self.trees:
            if root.is_dir():
                files.update(_tree_files(root, skip))
        return files


def _tree_files(root: Path, skip: tuple[str, ...]) -> Iterator[Path]:
    for path in scan_directory(root, recursive=True, select=DirectoryEntryKind.FILES, prune_directories=_PRUNED):
        # The catalogue writers' lock exists only while one of them runs, so it
        # carries no verdict input and may vanish between the scan and the read.
        if path.relative_to(root).parts[0] in skip or path.name == LOCK_FILENAME:
            continue
        yield path


def _stat(path: Path) -> tuple[int, int] | None:
    try:
        status = path.stat()
    except OSError:
        return None
    return (status.st_size, status.st_mtime_ns)


def engine_import_closure(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return the engine's files and every ``dev`` module they import, transitively.

    The graph is read statically, so the result is the same in every process that
    computes a key. Imports guarded by ``TYPE_CHECKING`` never run and are skipped;
    registry tooling is excluded for the reason given on ``_AUTHORITY_TOOLING``.

    Returns:
        Repository-relative POSIX paths, sorted.
    """
    pending: list[Path] = []
    for root in ENGINE_ROOTS:
        path = repo_root / root
        if path.is_file():
            pending.append(path)
        elif path.is_dir():
            pending.extend(
                scan_directory(
                    path,
                    pattern="*.py",
                    recursive=True,
                    select=DirectoryEntryKind.FILES,
                    prune_directories=("tests", *_PRUNED),
                )
            )
    development = repo_root / "dev"
    tooling = repo_root / _AUTHORITY_TOOLING

    def admit(path: Path) -> bool:
        return path.is_relative_to(development) and not path.is_relative_to(tooling)

    closure = static_import_closure(pending, (repo_root,), admit=admit)
    return tuple(sorted(path.relative_to(repo_root).as_posix() for path in closure))


def authority_compiler_closure(repo_root: Path = REPO_ROOT) -> tuple[str, ...]:
    """Return the product and ``dev`` modules outside the registry tooling that the authority compiler imports.

    The logical generation names the registry source, not the code that compiles
    it, so these files enter every key beside the generation and the tooling tree.

    Returns:
        Repository-relative POSIX paths, sorted.
    """
    tooling = repo_root / _AUTHORITY_TOOLING
    source = repo_root / "src"
    development = repo_root / "dev"

    def admit(path: Path) -> bool:
        return path.is_relative_to(source) or path.is_relative_to(development)

    closure = static_import_closure([repo_root / _AUTHORITY_COMPILER], (repo_root, source), admit=admit)
    # The walk passes through the tooling, which is hashed whole beside this closure.
    return tuple(sorted(path.relative_to(repo_root).as_posix() for path in closure if not path.is_relative_to(tooling)))


def configuring_environment() -> tuple[tuple[str, str], ...]:
    """Return the environment variables that can change what a sequence prints, sorted."""
    return tuple(
        sorted(
            (name, value)
            for name, value in os.environ.items()
            if (name.startswith(_ENVIRONMENT_PREFIX) or name in _ENVIRONMENT_NAMES) and name not in _TOOLING_ENVIRONMENT
        )
    )


def _record_path(key: str) -> Path:
    return dev_cache_dir(_CACHE_NAME) / f"{key}.json"


def reuse_forced_off() -> bool:
    """Return whether :data:`FORCE_ENV` asks every sequence to execute."""
    return bool(os.environ.get(FORCE_ENV))


class SequenceVerdicts:
    """The per-sequence verdict authority for one docs tree under one published authority.

    Construct it once per process, before any sequence executes: the corpus
    inputs are hashed once and their sizes and modification times captured, so
    recording a pass can confirm cheaply that nothing changed underneath it.
    """

    def __init__(
        self,
        *,
        docs_root: Path,
        goldens_root: Path | None,
        authority_identity: str,
        repo_root: Path = REPO_ROOT,
        contracts_root: Path | None = None,
        authority_files: tuple[Path, ...] = (),
    ) -> None:
        """Hash the corpus inputs once.

        Args:
            authority_files: The published authority's files; they enter the
                depfile so a republication re-runs the check, while the key
                carries only ``authority_identity``.
        """
        self._authority_files = authority_files
        self._docs_root = docs_root
        self._goldens_root = goldens_root
        self._contracts_root = contracts_root
        self._repo_root = repo_root.resolve()
        self._opened_ns = time.time_ns()
        self._trace = _InputTrace()
        self._closure: tuple[str, _InputTrace, dict[Path, tuple[int, int] | None], int] | None = None
        self._current: dict[Path, str] = {}
        self._current_listings: dict[Path, str] = {}
        # The sequence tree is keyed already: its shared seeds and fixtures by the
        # corpus, each contract and golden by its own sequence. Recording it as an
        # observed read would tie every sequence to the goldens of all the
        # sequences that ran before it in the same process.
        sequence_inputs = (docs_root / "_sequences", *(root for root in (goldens_root, contracts_root) if root))
        self._unrecorded = tuple(
            path.resolve()
            for path in (
                dev_cache_dir(_CACHE_NAME).parent,
                *(file.parent for file in authority_files),
                *sequence_inputs,
            )
        )
        with unobserved():
            self._corpus_key, self._snapshot = self._hash_corpus(authority_identity)

    def _hash_corpus(self, authority_identity: str) -> tuple[str, dict[Path, tuple[int, int] | None]]:
        repo_root = self._repo_root
        docs_root = self._docs_root
        digest = hashlib.sha256()
        digest.update(
            f"{_RECORD_FORMAT}\npython:{sys.version}\nplatform:{platform.system()}\n"
            f"authority:{authority_identity}\n".encode()
        )
        for name, value in configuring_environment():
            digest.update(f"environment:{name}={value}\n".encode())
        for relative in engine_import_closure(repo_root):
            self._trace.hash_tree(digest, repo_root / relative, label=f"engine-import/{relative}")
        for relative in authority_compiler_closure(repo_root):
            self._trace.hash_tree(digest, repo_root / relative, label=f"authority-compiler/{relative}")
        self._trace.hash_tree(digest, repo_root / "dev" / "docs" / "sequences", label="engine")
        self._trace.hash_tree(digest, repo_root / _AUTHORITY_TOOLING, label="authority-tooling")
        self._trace.hash_tree(digest, repo_root / "uv.lock", label="lock")
        sequences_root = docs_root / "_sequences"
        shared_skip = (_CONTRACTS_DIRECTORY, *self._golden_page_roots(sequences_root))
        self._trace.hash_tree(digest, sequences_root, label="sequences", skip=shared_skip)
        return digest.hexdigest(), self._trace.snapshot()

    def _product_closure(self) -> tuple[str, _InputTrace, dict[Path, tuple[int, int] | None], int]:
        """Hash the whole product source once, when an unobserved record or reuse first needs it."""
        if self._closure is None:
            trace = _InputTrace()
            digest = hashlib.sha256()
            hashed_ns = time.time_ns()
            with unobserved():
                for source_root in PRODUCT_SOURCE_ROOTS:
                    trace.hash_tree(digest, self._repo_root / source_root, label=source_root)
            self._closure = (digest.hexdigest(), trace, trace.snapshot(), hashed_ns)
        return self._closure

    def prepare_unobserved_run(self) -> None:
        """Hash the product closure now, before any sequence executes without observation."""
        self._product_closure()

    def _golden_page_roots(self, sequences_root: Path) -> tuple[str, ...]:
        """Name the top-level ``_sequences`` directories that hold committed goldens.

        Goldens live at ``<goldens root>/<page>/<sequence-id>.json``; a page's
        first docname segment is a docs section directory (``how-to``,
        ``explanation``), never ``seeds`` or ``fixtures``. When the goldens are
        redirected elsewhere, every committed ``_sequences`` subtree is shared.
        """
        if self._goldens_root is not None and self._goldens_root.resolve() != sequences_root.resolve():
            return ()
        sections = {
            path.relative_to(self._docs_root).parts[0]
            for path in scan_directory(self._docs_root, pattern="*.md", recursive=True, prune_directories=_PRUNED)
            if len(path.relative_to(self._docs_root).parts) > 1
        }
        return tuple(sorted(name for name in sections if not name.startswith("_")))

    @property
    def corpus_key(self) -> str:
        """The digest of every input the sequences share."""
        return self._corpus_key

    def _own_inputs(self, item: KeyedSequence) -> tuple[Path, Path]:
        contract = sequence_contract_path(
            item.page, item.sequence_id, docs_root=self._docs_root, contracts_root=self._contracts_root
        )
        return contract, golden_path(item.page, item.sequence_id, goldens_root=self._goldens_root)

    def key(self, item: KeyedSequence) -> str:
        """Return the content key of everything ``item``'s verdict depends on."""
        digest = hashlib.sha256()
        digest.update(f"corpus:{self._corpus_key}\npage:{item.page}\nsequence:{item.sequence_id}\n".encode())
        digest.update(item.sequence.model_dump_json().encode())
        for label, path in zip(("contract", "golden"), self._own_inputs(item), strict=True):
            try:
                content = path.read_bytes()
            except FileNotFoundError:
                digest.update(f"\nabsent:{label}\n".encode())
                continue
            digest.update(f"\n{label}:".encode())
            digest.update(hashlib.sha256(content).digest())
        return digest.hexdigest()

    def reused(self, item: KeyedSequence) -> str | None:
        """Describe the recorded clean verdict standing in for ``item``, or ``None`` to execute it."""
        if reuse_forced_off():
            return None
        with unobserved():
            key = self.key(item)
            try:
                document = json.loads(_record_path(key).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
            if not isinstance(document, dict) or document.get("verdict") != "clean" or document.get("key") != key:
                return None
            product = self._product_still_matches(document.get("product"))
        if product is None:
            return None
        return f"reused clean verdict {key[:12]} recorded {document.get('recorded_at')} ({product})"

    def _product_still_matches(self, product: object) -> str | None:
        """Return how the recorded product part still holds, or ``None`` when any of it moved."""
        if not isinstance(product, dict):
            return None
        mode = product.get("mode")
        if mode == _CLOSURE:
            return "whole product source unchanged" if product.get("digest") == self._product_closure()[0] else None
        files, listings = product.get("files"), product.get("listings")
        if mode != _OBSERVED or not isinstance(files, dict) or not isinstance(listings, dict):
            return None
        for relative, recorded in files.items():
            if not isinstance(relative, str) or self._current_file(self._repo_root / relative) != recorded:
                return None
        for relative, recorded in listings.items():
            if not isinstance(relative, str) or self._current_listing(self._repo_root / relative) != recorded:
                return None
        return f"{len(files)} observed product files unchanged"

    def _observed_inputs(self, item: KeyedSequence) -> Iterator[Path]:
        """Yield the product inputs ``item``'s current record was observed to read, for the depfile."""
        with unobserved():
            try:
                document = json.loads(_record_path(self.key(item)).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return
            if isinstance(document, dict):
                yield from _observed_paths(self._repo_root, document.get("product"))

    def _current_file(self, path: Path) -> str:
        if path not in self._current:
            self._current[path] = file_digest(path)
        return self._current[path]

    def _current_listing(self, path: Path) -> str:
        if path not in self._current_listings:
            self._current_listings[path] = listing_digest(path)
        return self._current_listings[path]

    def changed_inputs(self) -> tuple[Path, ...]:
        """Return the shared inputs added, removed, or whose size or modification time moved since construction."""
        moved = {path for path, before in self._snapshot.items() if _stat(path) != before}
        moved.update(self._trace.current_files() ^ self._trace.files)
        return tuple(sorted(moved))

    def record_clean(self, item: KeyedSequence, *, key: str, observation: Observation | None = None) -> None:
        """Record that ``item`` passed under ``key``, the key taken before it executed.

        With a complete ``observation`` the record holds every checkout file and
        listing the sequence's processes read, at the digest they had when read.
        Otherwise it holds the whole product source's digest. A failure to write
        costs only a future re-run.

        Raises:
            SequenceEngineError: When any input changed while the sequence ran;
                nothing is recorded.
        """
        with unobserved():
            changed = list(self.changed_inputs())
            if self.key(item) != key:
                changed.append(Path(f"{item.page}/{item.sequence_id}"))
            product = None if changed else self._recorded_product(observation, changed)
            if changed or product is None:
                detail = ", ".join(str(path) for path in changed[:5])
                raise SequenceEngineError(
                    f"cli-sequence inputs changed during execution ({detail}); "
                    f"no verdict was recorded for {item.page}/{item.sequence_id}"
                )
        record = _record_path(key)
        document = {
            "format": _RECORD_FORMAT,
            "key": key,
            "verdict": "clean",
            "page": item.page,
            "sequence_id": item.sequence_id,
            "recorded_at": datetime.now(UTC).isoformat(),
            "product": product,
        }
        staged = record.with_name(f"{record.name}.{os.getpid()}.tmp")
        try:
            record.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text(json.dumps(document), encoding="utf-8")
            staged.replace(record)
        except OSError:
            staged.unlink(missing_ok=True)

    def _recorded_product(self, observation: Observation | None, changed: list[Path]) -> dict[str, object] | None:
        """Return the product part to record, appending to ``changed`` any product file that moved."""
        if observation is not None and not observation.incomplete:
            files = self._recordable(observation.files)
            listings = self._recordable(observation.listings)
            # An observation that never saw the product package (rooted at
            # another checkout, or empty) keys on less than the sequence read;
            # the whole product source stands in instead.
            if OBSERVATION_SENTINEL in files:
                return {"mode": _OBSERVED, "files": files, "listings": listings}
        digest, trace, snapshot, hashed_ns = self._product_closure()
        changed.extend(path for path, before in snapshot.items() if _stat(path) != before)
        changed.extend(trace.current_files() ^ trace.files)
        started_ns = self._opened_ns if observation is None else observation.started_ns
        if hashed_ns > started_ns:
            # Hashed after sequences began executing: a file edited in between
            # would carry its new digest for a run that read the old bytes.
            changed.extend(path for path, status in snapshot.items() if status is None or status[1] >= started_ns)
        return None if changed else {"mode": _CLOSURE, "digest": digest}

    def _recordable(self, observed: dict[Path, str]) -> dict[str, str]:
        """Key the observed entries: checkout entries repository-relative, any other by its absolute path.

        The observer records a read outside the checkout only when it is not
        product source and not on its explicit allowlist, so such an entry is
        an input in its own right and is re-checked on reuse like any other.
        Entries under the development cache or the published authority are
        dropped: the key already carries them.
        """
        kept: dict[str, str] = {}
        for path, digest in observed.items():
            resolved = path.resolve()
            if any(resolved.is_relative_to(excluded) for excluded in self._unrecorded):
                continue
            if resolved.is_relative_to(self._repo_root):
                kept[resolved.relative_to(self._repo_root).as_posix()] = digest
            else:
                kept[resolved.as_posix()] = digest
        return dict(sorted(kept.items()))

    def dependency_paths(self, items: Iterable[KeyedSequence]) -> tuple[Path, ...]:
        """Return every file and directory the keys of ``items`` read, for a build-system depfile.

        Directories are listed so that a file added to or removed from a hashed
        tree, or a new page, re-runs the check.
        """
        closure = self._product_closure()[1]
        paths: set[Path] = {*self._trace.files, *self._trace.directories, *closure.files, *closure.directories}
        paths.update(path for path in self._trace.absent if path.parent.exists())
        paths.update(_page_inputs(self._docs_root))
        for item in items:
            for path in self._own_inputs(item):
                paths.add(path if path.exists() else path.parent)
            paths.update(self._observed_inputs(item))
        paths.add(Path(sys.executable))
        paths.update(self._authority_files)
        return tuple(sorted(paths))


def _observed_paths(repo_root: Path, product: object) -> Iterator[Path]:
    """Yield the files and listed directories an observed product part names, or an absent file's directory."""
    if not isinstance(product, dict) or product.get("mode") != _OBSERVED:
        return
    for part in ("files", "listings"):
        entries = product.get(part)
        if not isinstance(entries, dict):
            continue
        for relative in entries:
            if isinstance(relative, str):
                path = repo_root / relative
                yield path if path.exists() else path.parent


def _page_inputs(docs_root: Path) -> Iterator[Path]:
    """Yield every page and docs directory discovery reads directives from."""
    yield docs_root
    for page in scan_directory(docs_root, pattern="*.md", recursive=True, prune_directories=("_build", *_PRUNED)):
        yield page
        yield page.parent


def published_authority_identity() -> str:
    """Return the identity under which the published authority enters every verdict key.

    The authority enters as the logical generation its descriptor names: the
    identity of the registry source it was compiled from. Two publications of
    one source tree differ in database bytes, so the physical digest would make
    every fresh publication (each native build publishes its own) re-execute the
    whole corpus. The compiler that maps the generation to those bytes is a
    shared verdict input in its own right (``_AUTHORITY_TOOLING``), so the pair
    determines what every sequence reads. A reader's generation pin is not
    usable here, because it carries an incarnation drawn fresh for each reader.
    A stale authority is refused before it can key anything, so a clean verdict
    recorded under it can never be reused.

    Raises:
        SequenceEngineError: When the published authority is not current.
    """
    from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path
    from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

    require_current_authority()
    return AuthorityDescriptor.read(bundled_authority_descriptor_path()).logical_generation


def published_sequence_verdicts(
    *, docs_root: Path, goldens_root: Path | None, contracts_root: Path | None = None
) -> SequenceVerdicts:
    """Return the verdict authority for ``docs_root`` under the published authority the runner reads.

    Raises:
        SequenceEngineError: When the published authority is not current.
    """
    from cadrumo.domain.calculations.registry.authority_location import bundled_authority_descriptor_path

    return SequenceVerdicts(
        docs_root=docs_root,
        goldens_root=goldens_root,
        contracts_root=contracts_root,
        authority_identity=published_authority_identity(),
        authority_files=(bundled_authority_descriptor_path(),),
    )


def write_depfile(depfile: Path, *, target: Path, dependencies: Iterable[Path]) -> None:
    """Write a Makefile-syntax depfile naming ``target``'s ``dependencies``."""

    def escaped(path: Path) -> str:
        return path.resolve().as_posix().replace("$", "$$").replace("#", "\\#").replace(" ", "\\ ")

    lines = [f"{escaped(target)}: \\"]
    lines.extend(f"  {escaped(path)} \\" for path in dependencies)
    lines.append("")
    depfile.parent.mkdir(parents=True, exist_ok=True)
    depfile.write_text("\n".join(lines), encoding="utf-8", newline="\n")
