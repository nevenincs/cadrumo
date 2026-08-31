"""Inventory test: zero inline ``tzinfo is None`` guards survive in production code.

Every site that previously reimplemented UTC timezone validation inline
(``if value.tzinfo is None or value.utcoffset() is None: raise ...``) must
now delegate to :func:`~core.time.validate_utc_aware`.

This test walks the production source tree with :mod:`ast` and asserts that
no ``tzinfo is None`` comparisons appear outside the canonical UTC module
itself and outside test files. The composite guard quoted above is caught
through its ``tzinfo is None`` half, which is the shape the reimplementations
actually opened with.

Reach, stated precisely
-----------------------
The matcher recognises exactly one shape: an ``is None`` comparison whose
left-hand side is an attribute access ending in ``tzinfo``. It does **not**
recognise these near neighbours, and the difference is worth knowing before
reading a green run as proof the invariant holds:

- ``value.utcoffset() is None`` **alone**. One production site uses it —
  :mod:`~application.filing._import` tests a receipt instant for naivety and,
  when naive, attaches Madrid civil time rather than raising. That is not a
  reimplementation of the canonical validator: the validator *rejects* a naive
  value, whereas this site *repairs* one into a non-UTC civil zone that the
  AEAT importer contract requires. Neither :func:`~core.time.validate_utc_aware`
  nor :func:`~core.time.coerce_utc_aware` is a correct substitute there, so
  widening the matcher to this shape would report a legitimate site. Widening it
  *conditioned on the guarded branch raising* would separate the two cases on a
  structural difference rather than an allowlist, and is the open option here.
- ``value.tzinfo is not None`` — the inverted spelling, used for repair rather
  than rejection.
- ``not value.tzinfo`` and ``value.tzinfo == None`` — truthiness and equality
  spellings of the same question.

The bulk of the invariant is carried elsewhere regardless: the
:data:`~core.time.UtcInstant` annotated type enrols a field declaratively, so a
persisted instant is validated by its declaration rather than by an author
remembering to call the helper.

See Also:
    :mod:`~tests._inventory`
        Provides the shared production AST inventory consumed by the ratchet.
    :mod:`~core.time`
        Public home for the canonical UTC coercion and validation helpers.

A timezone-awareness check must delegate to the canonical validator so a
future rule change (leap-second handling, offset tolerance) is fixed once.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._inventory import SRC_CADRUMO, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_CADRUMO
_CANONICAL_UTC_MODULE = _SRC_ROOT / "core" / "time" / "utc.py"


def _tree_has_inline_tzinfo_guard(tree: ast.AST) -> bool:
    """Return True iff *tree* contains an inline ``tzinfo is None`` check."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        # Look for ``<expr>.tzinfo is None``
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            if not isinstance(op, ast.Is):
                continue
            if not (isinstance(comparator, ast.Constant) and comparator.value is None):
                continue
            # Check the left-hand side: it must be an attribute access ending in ``tzinfo``
            left = node.left if comparator is node.comparators[0] else None
            if left is None:
                # Handle chained comparisons — check all pairs
                for i, (op2, comp2) in enumerate(zip(node.ops, node.comparators, strict=False)):
                    if isinstance(op2, ast.Is) and isinstance(comp2, ast.Constant) and comp2.value is None:
                        lhs = node.left if i == 0 else node.comparators[i - 1]
                        if isinstance(lhs, ast.Attribute) and lhs.attr == "tzinfo":
                            return True
            else:
                if isinstance(left, ast.Attribute) and left.attr == "tzinfo":
                    return True
    return False


def test_no_inline_tzinfo_guards_in_production_code(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Assert zero ``tzinfo is None`` inline guards remain outside the UTC module.

    Consumes the shared production AST cache so the per-file parse cost
    is amortised across the full ratchet suite.
    """
    violations: list[str] = []
    canonical_utc = _CANONICAL_UTC_MODULE.resolve()

    for py_file, tree in production_ast_items(source_tree_ast):
        # Skip the canonical UTC module — it is the allowed home.
        if py_file.resolve() == canonical_utc:
            continue
        if _tree_has_inline_tzinfo_guard(tree):
            violations.append(str(py_file.relative_to(_SRC_ROOT.parent)))

    assert not violations, (
        f"Found {len(violations)} production file(s) with inline ``tzinfo is None`` guards "
        f"that must be migrated to validate_utc_aware:\n" + "\n".join(f"  {v}" for v in sorted(violations))
    )


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("if value.tzinfo is None:\n    raise E()\n", id="bare-guard"),
        pytest.param(
            "if value.tzinfo is None or value.utcoffset() is None:\n    raise E()\n",
            id="composite-guard-the-docstring-quotes",
        ),
        pytest.param("if self.captured_at.tzinfo is None:\n    raise E()\n", id="attribute-chain-lhs"),
        pytest.param("ok = value.tzinfo is None\n", id="assigned-not-branched"),
        pytest.param("return [v for v in xs if v.tzinfo is None]\n", id="nested-in-comprehension"),
    ),
)
def test_detector_fires_on_the_inline_guard(source: str) -> None:
    """Anti-tautology proof: the guard shape is planted and must be caught.

    This gate asserted an empty inventory for its whole life without ever
    demonstrating that a violation would be seen, which is the state in which a
    matcher and its stated contract can drift apart unnoticed. Sources are parsed
    in memory; no violation is committed to the tree.
    """
    assert _tree_has_inline_tzinfo_guard(ast.parse(source)), f"detector missed the planted guard in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("value = validate_utc_aware(value)\n", id="canonical-validator-call"),
        pytest.param("value = coerce_utc_aware(value)\n", id="canonical-coercion-call"),
        pytest.param("if value.year is None:\n    raise E()\n", id="different-attribute"),
        pytest.param("if value is None:\n    raise E()\n", id="plain-none-guard"),
        pytest.param("value = value.replace(tzinfo=UTC)\n", id="tzinfo-as-keyword-not-a-guard"),
    ),
)
def test_detector_stays_silent_on_non_guards(source: str) -> None:
    """The other direction: a canonical call or an unrelated ``is None`` is not a guard.

    The ``tzinfo=UTC`` keyword case matters: ``tzinfo`` appears in the source but
    as a constructor argument, not as the left-hand side of a naivety test.
    """
    assert not _tree_has_inline_tzinfo_guard(ast.parse(source))
