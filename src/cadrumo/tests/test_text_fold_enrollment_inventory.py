"""Inventory gate for the canonical accent-folding primitive.

Production modules under ``src/cadrumo/`` must not call
``unicodedata.normalize("NFKD", ...)`` (or any of the other three Unicode
normalization forms) directly. All callers must delegate to
:func:`~core.text_fold.fold_diacritics`.

This mirrors :mod:`~cadrumo.tests.test_decimal_enrollment_inventory`: nine
call sites across ``core``, ``application``, ``domain``, and ``adapters``
independently hand-rolled the same NFKD-decompose-and-strip-combining-marks
routine before that helper existed, with two of them diverging into a
materially different (and, at one live-automation safety site, silently
weaker) algorithm. An AST gate that reds on the next hand-rolled call keeps
the fold from re-fragmenting the way the decimal coercions had to be swept up
after the fact.

See Also:
    :mod:`~core.text_fold`
        Canonical accent-folding primitive.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by this ratchet.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

import pytest

from .inventory import SRC_CADRUMO, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CANONICAL_MODULE = SRC_CADRUMO / "core" / "text_fold.py"
"""The one module allowed to call ``unicodedata.normalize`` directly."""

_NORMALIZATION_FORMS = frozenset({"NFC", "NFD", "NFKC", "NFKD"})


def _is_unicodedata_normalize_call(node: ast.AST) -> TypeGuard[ast.expr]:
    """Match ``unicodedata.normalize("NFKD", ...)`` and the bare-imported form.

    Keyed on the call shape (a function literally named ``normalize`` whose
    first positional argument is one of the four normalization-form string
    literals), the same argument-shape heuristic
    :mod:`~cadrumo.tests.test_decimal_enrollment_inventory` uses for
    ``Decimal(str(...))`` -- this cannot resolve full import provenance, but
    an unrelated ``.normalize("NFKD")`` call on some other type is not a
    realistic false positive in this codebase.
    """
    return (
        isinstance(node, ast.Call)
        and leaf_name(node.func) == "normalize"
        and len(node.args) >= 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value in _NORMALIZATION_FORMS
    )


def _collect_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline normalize call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if path == _CANONICAL_MODULE:
            continue
        for node in ast.walk(tree):
            if _is_unicodedata_normalize_call(node):
                assert isinstance(node, ast.Call)
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    return violations


def test_no_inline_unicode_normalize_call(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Inline ``unicodedata.normalize("NFKD", ...)`` must be zero in production code.

    All known sites delegate diacritic folding to ``fold_diacritics`` from
    ``cadrumo.core.text_fold``. Any new inline call is a regression -- either
    a re-fragmentation of the fold this gate exists to prevent, or a genuine
    need for a different normalization form that belongs in the canonical
    module, not scattered back across the tree.
    """
    violations = _collect_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline unicodedata.normalize(...) call(s) found in "
            f"production code:\n  {joined}\n\n"
            "Replace each call with fold_diacritics() from cadrumo.core.text_fold "
            "(composed with your own trailing transform and casing).",
        )


def test_gate_reds_on_a_planted_inline_normalize_call(tmp_path: Path) -> None:
    """Anti-tautology proof: the gate really fails on the shape it forbids."""
    module = tmp_path / "planted.py"
    module.write_text(
        "\n".join(
            (
                "import unicodedata",
                "",
                "",
                "def hand_rolled_fold(text: str) -> str:",
                '    decomposed = unicodedata.normalize("NFKD", text)',
                '    return "".join(c for c in decomposed if not unicodedata.combining(c))',
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    violations = [f"{node.lineno}" for node in ast.walk(tree) if _is_unicodedata_normalize_call(node)]

    assert violations == ["5"], violations
