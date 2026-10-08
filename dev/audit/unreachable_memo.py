"""Share immutable AST parses and walks for exactly one reachability scan."""

from __future__ import annotations

import ast
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path

from dev.quality.cyclic_gc import cyclic_gc_paused


@dataclass
class _ScanMemo:
    """Parses and node walks shared by every pass of one scan.

    The passes read the same few thousand trees independently, and each used to
    re-parse and re-walk them, which made one scan minutes of repeated work. The
    memo lives only for one :func:`shared_scan_memo` block, so a file edited
    between scans is read afresh. Trees are never mutated, so sharing is safe.
    """

    trees: dict[Path, ast.Module] = field(default_factory=dict)
    walks: dict[int, tuple[ast.AST, tuple[ast.AST, ...]]] = field(default_factory=dict)


_SCAN_MEMO: ContextVar[_ScanMemo | None] = ContextVar("unreachable_code_scan_memo", default=None)


@contextmanager
def shared_scan_memo() -> Iterator[None]:
    """Share parses and node walks among every pass run inside the block.

    A scan that composes several of this module's passes over the same trees
    opens one block around them; each tree is then parsed and walked once. The
    memo is discarded on exit, so a later scan reads edited files afresh. The
    cyclic collector is paused for the block, because the memo keeps every tree
    and walk alive at once and each full collection would only re-traverse them.
    """
    token = _SCAN_MEMO.set(_ScanMemo())
    try:
        with cyclic_gc_paused():
            yield
    finally:
        _SCAN_MEMO.reset(token)


def _walked(tree: ast.AST) -> Iterable[ast.AST]:
    """Every node under ``tree`` in ``ast.walk`` order, walked once per scan."""
    memo = _SCAN_MEMO.get()
    if memo is None:
        return ast.walk(tree)
    entry = memo.walks.get(id(tree))
    if entry is None or entry[0] is not tree:
        entry = (tree, tuple(ast.walk(tree)))
        memo.walks[id(tree)] = entry
    return entry[1]


def parse_module(path: Path) -> ast.Module:
    """Parse one source file into a module tree, once per scan."""
    memo = _SCAN_MEMO.get()
    if memo is not None and (cached := memo.trees.get(path)) is not None:
        return cached
    tree = ast.parse(path.read_bytes(), filename=str(path))
    if memo is not None:
        memo.trees[path] = tree
    return tree
