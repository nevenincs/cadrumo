"""Refuse a generated artefact whose source tree moved while it was produced.

A generator that walks the source tree assumes the tree holds still. In a
shared worktree it does not: a peer lands a relocation mid-run, and the
artefact records a module that existed when the walk began and not when it
ended. The output looks well-formed, its own `--check` fails on the next
invocation, and the failure names the missing module rather than the race that
produced it.

Every quietness signal available before a run -- modification times, parse
status, counts of recently touched files -- describes a window that has already
closed. The generator ingests the tree during a window that has not yet opened,
so no amount of looking beforehand settles it. This closes that gap from the
other side: fingerprint before, fingerprint after, and refuse the output when
the two disagree.

Refusing is the whole point. A regeneration that silently absorbs half-landed
work is worse than one that does not run, because the artefact then carries the
race forward as fact and the next reader has no way to tell.

See Also:
    :mod:`dev.quality.registry_authority_consumer_census`
        One of the generators this guards.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

__all__ = ["TreeMovedDuringGenerationError", "refuse_if_tree_moves", "tree_fingerprint"]

_SOURCE_ROOTS: tuple[str, ...] = ("src", "dev")


class TreeMovedDuringGenerationError(RuntimeError):
    """The source tree changed while an artefact was being generated."""


def tree_fingerprint(root: Path, *, roots: Sequence[str] = _SOURCE_ROOTS) -> str:
    """Fingerprint every Python file the generators read.

    Keyed on path, size and modification time rather than content: the point is
    to notice that a file MOVED, and a rename changes the path set even when
    every byte survives somewhere else. Reading content would also cost a full
    tree read per fingerprint, twice per run, on a share where that is the
    dominant cost.
    """
    digest = hashlib.sha256()
    for name in roots:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                stat = path.stat()
            except OSError:
                # A file that vanished between the walk and the stat is itself
                # the movement this guard exists to catch, so record the fact
                # rather than skipping it.
                digest.update(f"{path}:GONE\n".encode())
                continue
            digest.update(f"{path}:{stat.st_size}:{stat.st_mtime_ns}\n".encode())
    return digest.hexdigest()


@contextmanager
def refuse_if_tree_moves(root: Path, *, roots: Sequence[str] = _SOURCE_ROOTS) -> Iterator[None]:
    """Run a generation and refuse its output if the tree moved underneath it.

    Raises:
        TreeMovedDuringGenerationError: When the fingerprint taken before the
            body differs from the one taken after, meaning the artefact may
            describe a tree that no longer exists.
    """
    before = tree_fingerprint(root, roots=roots)
    yield
    after = tree_fingerprint(root, roots=roots)
    if before != after:
        raise TreeMovedDuringGenerationError(
            "the source tree changed while this artefact was being generated, so it may record "
            "modules that no longer exist. Nothing was written. Re-run when no other lane is "
            "editing the tree; a quiet interval measured BEFORE the run does not establish one "
            "that lasts THROUGH it."
        )
