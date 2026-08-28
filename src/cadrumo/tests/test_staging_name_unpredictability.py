"""Inventory test: no production module stages through a guessable temporary name.

A staging sibling is the file a durable write lives in between "the bytes are
complete" and "the operator can see them". For an export it is a complete,
cleartext, filing-grade artefact sitting in a directory the operator chose,
under a name they were never told. Two properties keep that safe: the name
must not be computable in advance from the destination, and the writer must
discard it on every exit that does not publish.

This ratchet enforces the first. It walks the production source tree and
asserts that every constructed name ending in ``.tmp`` interpolates a call --
``os.getpid()``, ``uuid4().hex``, :func:`secrets.token_hex` -- rather than
appending a constant suffix to a path the caller supplied. The modelo fichero
export staged at ``{output_path.name}.tmp`` beside the operator's ``--output``,
which anything watching that directory could compute before the export ran.

Reach, stated precisely
-----------------------
The matcher recognises two construction shapes and deliberately not a third:

- ``expr + ".tmp"`` -- concatenation onto a caller-supplied name. Zero entropy
  by construction, so it is reported unconditionally.
- an f-string whose text ends in ``.tmp`` -- reported unless at least one of
  its substitutions contains a call. A substitution that is a plain attribute
  or name (``f"{path.name}.tmp"``) carries no entropy and is reported.

A bare ``".tmp"`` constant is NOT reported. Every remaining production use of
one is a *reader*, not a writer: a maintenance sweep matching orphan staging
files by suffix, or a ``suffix=`` argument handed to :mod:`tempfile`, whose
own name generation supplies the entropy. Reporting those would say nothing
about predictability and would push authors toward an allowlist.

The ratchet gates the NAME, not the cleanup discipline; the discard-on-every-
exit half is enforced by real-behaviour tests over the canonical tier in
``core/tests/test_atomic_write.py``.

See Also:
    :mod:`~core.atomic_write`
        The canonical durable-write tiers. Its deferred-publish tier exists so
        a producer that must build the file itself still gets the hardened
        staging name and the discard guarantee instead of open-coding both.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_CADRUMO, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_STAGING_SUFFIX = ".tmp"


def _ends_with_staging_suffix(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(_STAGING_SUFFIX)


def _joined_str_ends_with_staging_suffix(node: ast.JoinedStr) -> bool:
    return bool(node.values) and _ends_with_staging_suffix(node.values[-1])


def _interpolates_a_call(node: ast.JoinedStr) -> bool:
    """Whether any substitution contains a call, the only entropy source in use."""
    return any(
        isinstance(descendant, ast.Call)
        for value in node.values
        if isinstance(value, ast.FormattedValue)
        for descendant in ast.walk(value)
    )


def _is_predictable_staging_construction(node: ast.AST) -> bool:
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, ast.Add) and _ends_with_staging_suffix(node.right)
    if isinstance(node, ast.JoinedStr):
        return _joined_str_ends_with_staging_suffix(node) and not _interpolates_a_call(node)
    return False


def _predictable_staging_constructions(tree: ast.AST) -> list[int]:
    found: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp | ast.JoinedStr) and _is_predictable_staging_construction(node):
            found.append(node.lineno)
    return found


def test_no_production_module_builds_a_predictable_staging_name(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Every staged temporary name must carry entropy the destination cannot supply."""
    offenders: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        offenders.extend(
            f"{path.relative_to(SRC_CADRUMO).as_posix()}:{line}" for line in _predictable_staging_constructions(tree)
        )

    assert offenders == [], (
        "these sites build a staging name a caller can compute in advance; "
        "stage through cadrumo.core.atomic_write instead: " + ", ".join(offenders)
    )
