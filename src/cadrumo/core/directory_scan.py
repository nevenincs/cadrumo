"""Canonical directory-scan primitive built on ``os.scandir``.

Every module in the tree that needs "the files under this directory" resolves
it here, rather than reaching for :meth:`pathlib.Path.iterdir`,
:meth:`pathlib.Path.glob`, or :meth:`pathlib.Path.rglob` directly.

The case for centralising is consistency, not raw speed, and it is worth
being exact about that. ``os.scandir`` used to be dramatically faster than
:meth:`pathlib.Path.rglob`, because pathlib materialised a ``Path`` per entry
and re-stat'ed it to decide whether to descend. Python 3.13 rewrote globbing
onto ``glob._Globber``, which calls ``os.scandir`` itself and reuses the
directory entry rather than re-stat'ing -- so that gap has largely closed.
Measured on the repository's own tree (4,985 ``.py`` files, warm cache,
best of ten): a bare ``scandir`` walk 0.19s, this primitive 0.23s,
``sorted(Path.rglob("*.py"))`` 0.27s. Parity, not an order of magnitude.

What this module still buys is real, and none of it is throughput:

* One walk with one ordering rule, instead of every caller re-deciding
  whether to wrap ``sorted()`` and what to sort.
* *prune_directories*, which ``Path.rglob`` cannot express at all. Pruning
  happens BEFORE descending, so an excluded directory costs one ``is_dir``
  check rather than a full subtree walk -- which is what makes excluding a
  large data tree cheap rather than merely correct, and is where a genuine
  order-of-magnitude win is still available.
* An explicit, tested answer on the three semantics that silently differ
  between platforms and call styles: sort order, missing directories, and
  symlinks.

Nothing here is memoised. A cached listing of a directory under construction
is simply wrong, and production callers write to the directories they scan;
the one place in the tree that can safely cache a walk (the immutable source
tree during a test session) owns that cache itself.

Two return shapes exist, and the split is deliberate:

* :func:`scan_directory` materialises and sorts, for the overwhelmingly common
  caller that wanted a deterministic listing and was wrapping its own
  ``sorted(...)`` around a glob.
* :func:`iter_directory` stays lazy, for the caller that asks
  ``any(...)`` or breaks out of a loop early. Handing those a sorted tuple
  would walk the whole tree to answer a question the first entry settles.

The default arguments reproduce the pathlib call they replace exactly, so a
mechanical migration cannot silently change what a call site sees:
``scan_directory(root)`` is ``root.iterdir()``,
``scan_directory(root, pattern=p)`` is ``root.glob(p)``, and
``scan_directory(root, pattern=p, recursive=True)`` is ``root.rglob(p)``.
Narrowing to files or directories, and pruning, are opt-in.
"""

from __future__ import annotations

import fnmatch
import os
import re
from collections.abc import Callable, Collection, Iterator
from enum import StrEnum
from pathlib import Path

from .errors import CoreValidationError


class DirectoryEntryKind(StrEnum):
    """Which directory entries a scan yields.

    :attr:`ALL` is the default because it is what the pathlib calls this
    module replaces actually do: ``iterdir()``, ``glob("*")``, and even
    ``glob("*.toml")`` all yield directories alongside files, and a
    directory whose name matches the pattern is a real occurrence rather
    than a hypothetical one. A scan that narrowed to files by default would
    silently drop those entries at every migrated call site.
    """

    FILES = "files"
    """Entries that are not directories."""

    DIRECTORIES = "directories"
    """Entries that are directories."""

    ALL = "all"
    """Every entry, matching what ``iterdir``, ``glob`` and ``rglob`` yield."""


def scan_directory(
    root: Path,
    *,
    pattern: str | None = None,
    recursive: bool = False,
    select: DirectoryEntryKind = DirectoryEntryKind.ALL,
    prune_directories: Collection[str] = (),
    require_root: bool = False,
) -> tuple[Path, ...]:
    """Return the entries under *root*, sorted, walked with ``os.scandir``.

    The eager shape. Ordering is ``sorted()`` over :class:`~pathlib.Path`
    objects, which compares on the case-normalised string form -- so on
    Windows ``B.toml`` sorts before ``a.toml``, exactly as it would have
    under ``sorted(root.glob(...))``. Sorting the string forms instead
    would be case-sensitive and reorder mixed-case trees, which the
    determinism gates would catch as drift.

    Args:
        root: Directory to scan. Results keep *root*'s relative or absolute
            form, as the pathlib calls do; nothing is resolved.
        pattern: Single-segment glob (``"*.toml"``, ``"test_*.py"``,
            ``"modelo-*.json"``) matched against each entry's bare name.
            ``None`` matches every entry. See :func:`iter_directory` for the
            matching semantics and the refused pattern shapes.
        recursive: Descend into subdirectories. Descent is unconditional --
            *pattern* filters what is yielded, never what is entered, which
            is how ``rglob`` behaves.
        select: Narrow to files or to directories. Defaults to
            :attr:`DirectoryEntryKind.ALL`, the pathlib-identical shape.
        prune_directories: Bare directory names never entered and never
            yielded, checked before descending. This is caller policy, not
            a default: no name is pruned unless named here, so a scan
            reproduces its pathlib equivalent until the caller opts out.
        require_root: Raise the underlying :exc:`OSError` when *root* is
            missing or is not a directory, instead of returning empty.

    Returns:
        Sorted paths of every selected entry beneath *root*.

    Raises:
        CoreValidationError: *pattern* is empty, spans path segments, or
            uses ``**``.
        OSError: *root* could not be scanned and *require_root* is set.
    """
    return tuple(
        sorted(
            _scan(
                root,
                pattern=pattern,
                recursive=recursive,
                select=select,
                prune_directories=prune_directories,
                require_root=require_root,
                ordered=False,
            )
        )
    )


def iter_directory(
    root: Path,
    *,
    pattern: str | None = None,
    recursive: bool = False,
    select: DirectoryEntryKind = DirectoryEntryKind.ALL,
    prune_directories: Collection[str] = (),
    require_root: bool = False,
) -> Iterator[Path]:
    """Yield the entries under *root* lazily, walked with ``os.scandir``.

    The lazy sibling of :func:`scan_directory`, for the caller that stops
    early: ``any(iter_directory(root, pattern="*.pdf"))`` settles on the
    first match instead of walking the tree to build a listing it discards.

    Ordering is a pre-order traversal, with each directory's own entries
    yielded in case-normalised name order and a subdirectory's contents
    yielded at the point that subdirectory appears. That is deterministic,
    but it is NOT the ordering :func:`scan_directory` returns: a global sort
    over full paths interleaves depths differently, and no lazy walk can
    produce it without materialising everything first. A caller that needs
    the sorted listing wants the eager shape.

    Argument validation is eager -- a refused *pattern* raises from this
    call, not from the first ``next()`` -- while the walk itself is lazy.
    Each directory's entries are read and its handle closed before any is
    yielded, so a consumer can delete a directory it is iterating without
    tripping a Windows sharing violation.

    Missing directories yield nothing rather than raising, unless
    *require_root* is set. ``Path.glob`` and ``Path.rglob`` silently yield
    nothing for a missing directory while ``os.scandir`` raises
    :exc:`FileNotFoundError`, and every existing call site was written
    against the silent behaviour. An :exc:`OSError` encountered *below* the
    root -- an unreadable subdirectory, a directory removed mid-walk --
    always skips that subtree, which is what pathlib's own walk does; only
    the root's failure is configurable.

    Pattern matching goes through :func:`fnmatch.translate` over
    :func:`os.path.normcase`-folded text, which reproduces
    :meth:`pathlib.Path.glob` exactly: case-insensitive on Windows,
    case-sensitive on POSIX, and matching leading-dot names that a shell
    would hide. :func:`fnmatch.fnmatchcase` would instead be case-sensitive
    everywhere and would quietly stop matching ``*.toml`` against a
    ``.TOML`` file that ``glob`` finds today.

    Multi-segment patterns (``"*/*.toml"``) and ``**`` are refused rather
    than approximated. Recursion is spelled by *recursive*, and a pattern
    silently matched against bare names alone would find nothing at all for
    ``"*/*.toml"`` while looking like it worked.

    Symlinks are classified and traversed with ``follow_symlinks=False``, so
    a symlink loop cannot hang the walk -- matching ``rglob``, which stopped
    following directory symlinks in Python 3.13. One divergence follows and
    is deliberate: a symlink pointing at a directory is not a directory
    here, so it appears under :attr:`DirectoryEntryKind.FILES` and not under
    :attr:`DirectoryEntryKind.DIRECTORIES`, whereas ``Path.is_dir()``
    resolves the target and would say otherwise. The rule is exact: an entry
    is a directory precisely when the walk would descend into it.

    Args:
        root: Directory to scan. Results keep *root*'s relative or absolute
            form; nothing is resolved.
        pattern: Single-segment glob matched against each entry's bare name,
            or ``None`` to match every entry.
        recursive: Descend into subdirectories.
        select: Narrow to files or to directories.
        prune_directories: Bare directory names never entered and never
            yielded.
        require_root: Raise the underlying :exc:`OSError` when *root* is
            missing or is not a directory, instead of yielding nothing.

    Yields:
        Paths of every selected entry beneath *root*.

    Raises:
        CoreValidationError: *pattern* is empty, spans path segments, or
            uses ``**``.
        OSError: *root* could not be scanned and *require_root* is set.
    """
    return _scan(
        root,
        pattern=pattern,
        recursive=recursive,
        select=select,
        prune_directories=prune_directories,
        require_root=require_root,
        ordered=True,
    )


def _scan(
    root: Path,
    *,
    pattern: str | None,
    recursive: bool,
    select: DirectoryEntryKind,
    prune_directories: Collection[str],
    require_root: bool,
    ordered: bool,
) -> Iterator[Path]:
    """Validate the arguments eagerly, then hand back the lazy walk.

    Splitting validation from the generator is what lets a refused pattern
    raise from the public call rather than from the caller's first
    ``next()``, where the traceback would point at the loop instead of the
    mistake.

    *ordered* asks each directory's entries to be name-sorted as they are
    read. :func:`iter_directory` needs that -- it is the only ordering its
    consumer will ever see -- while :func:`scan_directory` sorts the whole
    result afterwards and would simply be paying for the work twice.
    """
    matches = _compile_name_matcher(pattern)
    pruned = frozenset(prune_directories)
    root_entries = _read_entries(os.fspath(root), propagate=require_root, ordered=ordered)
    if root_entries is None:
        return iter(())
    return _walk(root_entries, matches=matches, recursive=recursive, select=select, pruned=pruned, ordered=ordered)


def _walk(
    root_entries: list[os.DirEntry[str]],
    *,
    matches: Callable[[str], bool] | None,
    recursive: bool,
    select: DirectoryEntryKind,
    pruned: frozenset[str],
    ordered: bool,
) -> Iterator[Path]:
    """Pre-order walk over an explicit stack of directory listings.

    An explicit stack rather than a recursive generator: descent depth is
    bounded by the tree, not by the interpreter's recursion limit, so a
    deeply nested extracted archive cannot raise where ``rglob`` would not.
    """
    stack: list[Iterator[os.DirEntry[str]]] = [iter(root_entries)]
    while stack:
        entry = next(stack[-1], None)
        if entry is None:
            stack.pop()
            continue
        is_directory = entry.is_dir(follow_symlinks=False)
        if is_directory and entry.name in pruned:
            continue
        if _is_selected(is_directory, select) and (matches is None or matches(entry.name)):
            yield Path(entry.path)
        if is_directory and recursive:
            child_entries = _read_entries(entry.path, propagate=False, ordered=ordered)
            if child_entries is not None:
                stack.append(iter(child_entries))


def _is_selected(is_directory: bool, select: DirectoryEntryKind) -> bool:
    """Whether an entry of this kind passes the *select* narrowing."""
    if select is DirectoryEntryKind.ALL:
        return True
    if select is DirectoryEntryKind.DIRECTORIES:
        return is_directory
    return not is_directory


def _read_entries(path: str, *, propagate: bool, ordered: bool) -> list[os.DirEntry[str]] | None:
    """Read one directory into a list, optionally name-ordered.

    Returns ``None`` when the directory could not be read and *propagate* is
    unset, which is the silent-empty behaviour ``Path.glob`` gives for a
    missing directory.

    The sort key is the case-normalised name, matching how
    :class:`~pathlib.Path` compares, with the raw name breaking ties so two
    entries differing only in case cannot swap between runs.

    The listing is materialised and the directory handle closed before the
    caller sees any entry, whether or not it is sorted. That is what lets a
    consumer delete a directory it is part-way through iterating without
    tripping a Windows sharing violation.
    """
    try:
        with os.scandir(path) as entries:
            if not ordered:
                return list(entries)
            return sorted(entries, key=lambda entry: (os.path.normcase(entry.name), entry.name))
    except OSError:
        if propagate:
            raise
        return None


def _compile_name_matcher(pattern: str | None) -> Callable[[str], bool] | None:
    """Compile *pattern* into a bare-name predicate, or ``None`` to match all.

    Compiling once per scan rather than calling :func:`fnmatch.fnmatch` per
    entry: the two are equivalent by construction -- ``fnmatch`` is defined
    as this exact translate-over-normcase -- but a tree-wide walk would
    otherwise re-normalise the pattern once per file.
    """
    if pattern is None:
        return None
    if not pattern:
        raise CoreValidationError("directory scan pattern must not be empty; pass pattern=None to match every entry")
    if "**" in pattern:
        raise CoreValidationError(
            f"directory scan pattern {pattern!r} uses '**'; spell recursion with recursive=True instead"
        )
    if "/" in pattern or "\\" in pattern:
        raise CoreValidationError(
            f"directory scan pattern {pattern!r} spans path segments; patterns match one bare entry name, "
            "so a multi-segment glob must be expressed as nested scans"
        )
    compiled = re.compile(fnmatch.translate(os.path.normcase(pattern)))
    return lambda name: compiled.match(os.path.normcase(name)) is not None


__all__ = ["DirectoryEntryKind", "iter_directory", "scan_directory"]
