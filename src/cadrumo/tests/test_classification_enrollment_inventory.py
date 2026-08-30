"""Inventory gate for the canonical inner-envelope classification predicate.

Production modules under ``src/cadrumo/`` must not hand-roll a ``.classification``
comparison (``envelope.classification != expected``, ``entry.classification is not
definition.sensitivity``, and every operand order and operator variant of that
same question) inline. All callers must delegate to
:func:`~adapters.persistence.storage.inner_envelope_classification_is_expected`.

This mirrors :mod:`~cadrumo.tests.test_decimal_enrollment_inventory` and
:mod:`~cadrumo.tests.test_text_fold_enrollment_inventory`: twenty-nine call sites
across ``adapters`` and ``application`` hand-rolled the same stored-vs-expected
classification comparison independently before this predicate existed, in six
distinct shapes (``!=`` vs ``is not``, a bare :class:`ClassificationError` vs six
domain-specific ``*PersistenceError`` subclasses, a raw f-string message vs a
typed ``context=``/``translated_message=`` pair, and a shared i18n key vs three
separately-minted ones for the identical condition). An inventory keyed on the
RAISE (``grep "raise ClassificationError"``) could not find the six sites that
wrap the comparison in a different exception class — that is exactly why this
gate is keyed on the COMPARISON itself, not on any particular raise shape.

Four sites match the same AST shape without being this predicate's concept, and
are recorded as reasoned exemptions below rather than routed through it. Two
compare two ``.classification`` attributes to each other rather than a stored
value against a caller-declared expectation — an internal PEER-coherence check
(index vs envelope vs sealed record; envelope vs its own payload), with no
single "expected" operand. One is a read-time layout DISPATCH branch, not a
validation gate that raises on mismatch. One compares an unrelated
``BusinessClassification``-valued ledger filter that happens to share the
attribute name — AST shape cannot see attribute *types*, the same documented
blind spot :mod:`~cadrumo.tests._decimal_parse_inventory` names for its own
string-vs-attribute discriminator.

See Also:
    :func:`~adapters.persistence.storage.inner_envelope_classification_is_expected`
        Canonical non-raising equality predicate every call site must delegate to.
    :mod:`~cadrumo.tests._inventory`
        Shared production AST inventory surface used by this ratchet.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

import pytest

from ._inventory import SRC_CADRUMO, aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CANONICAL_MODULE = "adapters/persistence/storage/_schema_lineage.py"
"""The one module allowed to declare the classification equality itself.

Its own predicate body compares two bare parameter names (``stored is
expected``), never a ``.classification`` attribute, so it does not trip the
detector below in practice -- this exclusion is defence-in-depth, matching the
precedent in :mod:`~cadrumo.tests.test_text_fold_enrollment_inventory`.
"""

_CLASSIFICATION_COMPARE_EXEMPTIONS: Mapping[tuple[str, str], str] = {
    ("adapters/persistence/storage/secret_store/store.py", "get"): (
        "Three-way peer-coherence check (index entry vs envelope vs sealed record) "
        "with no single 'expected' operand -- not the stored-vs-expected shape this "
        "predicate covers. See the surrounding comment for the class-triad rationale."
    ),
    ("adapters/persistence/storage/blob_store/_blob_store.py", "_coherent_blob_manifest"): (
        "Envelope-vs-payload internal coherence check on one manifest (a manifest "
        "states its classification twice and this refuses the two disagreeing), not "
        "a stored-vs-caller-declared-expected_class comparison."
    ),
    ("adapters/persistence/storage/blob_store/_blob_store.py", "get"): (
        "Read-time layout DISPATCH (route to the plaintext or ciphertext read path), "
        "not a validation gate that raises on mismatch. SensitivityClass.CORPUS here "
        "is a branch key, not a caller-declared expectation to enforce."
    ),
    ("application/ledger/review_projection.py", "_filter_ledger_review_rows"): (
        "query.classification here is a BusinessClassification-valued ledger review "
        "filter, not a SensitivityClass -- an unrelated taxonomy that happens to share "
        "the attribute name. AST shape alone cannot distinguish the two attribute "
        "types (the documented blind spot in cadrumo.tests._decimal_parse_inventory)."
    ),
}
"""Reasoned exemptions, keyed by ``(path, enclosing function)``.

Keyed by function rather than line number so an unrelated edit in the same file
cannot silently slide a site out of its exemption, and so a *new* bad comparison
added to an already-exempt file still fails. Every key is proven to still
resolve to a real site by :func:`test_classification_exemptions_are_all_live`.
"""


def _is_classification_attr(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "classification"


def _is_live_reference(node: ast.expr) -> bool:
    """Return whether *node* is a name/attribute reference rather than a literal.

    The discriminator that keeps this detector narrow to the ``SensitivityClass``
    concept: every one of the twenty-nine known sites compares
    ``.classification`` against a live typed reference (``expected_class``,
    ``definition.sensitivity``, ``SensitivityClass.FINANCIAL``, ...), never a
    literal. Unrelated ``.classification`` attributes elsewhere in the tree
    (``BusinessClassification``, a relation-fold taxonomy, a remote-state-guard
    taxonomy) are compared against ``None`` or a bare string constant instead --
    ``query.classification is not None``, ``record.classification ==
    "canonical_relation_prefill"``. Requiring the OTHER operand to be a live
    reference excludes every one of those false positives while keeping every
    real site, the same shape of narrowing
    :mod:`~cadrumo.tests._decimal_parse_inventory` documents for its own
    string-vs-attribute discriminator.
    """
    return isinstance(node, ast.Name | ast.Attribute)


def _is_classification_compare(node: ast.AST) -> TypeGuard[ast.expr]:
    """Match ``<expr>.classification <op> <live reference>`` for ``op`` in ``==``/``!=``/``is``/``is not``.

    Only one side needs to be the ``.classification`` attribute access -- every
    known site puts it on the left, but the detector does not assume that, the
    same defensive posture :mod:`~cadrumo.tests.test_decimal_enrollment_inventory`
    takes on argument position. The OTHER side must be a live reference (see
    :func:`_is_live_reference`), not a literal, or the match is not this
    predicate's concept.
    """
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    if not isinstance(node.ops[0], ast.Eq | ast.NotEq | ast.Is | ast.IsNot):
        return False
    left, right = node.left, node.comparators[0]
    if _is_classification_attr(left):
        return _is_live_reference(right)
    if _is_classification_attr(right):
        return _is_live_reference(left)
    return False


def _enclosing_name(node: ast.AST | None) -> str:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return node.name
    return "<module>"


def classification_compare_sites(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    """Return ``(lineno, enclosing function name)`` for each hand-rolled classification compare."""
    if not isinstance(tree, ast.Module):
        return ()
    found: list[tuple[int, str]] = []

    def walk(current: ast.AST, enclosing: ast.AST | None) -> None:
        if isinstance(current, ast.FunctionDef | ast.AsyncFunctionDef):
            for child in ast.iter_child_nodes(current):
                walk(child, current)
            return
        if _is_classification_compare(current):
            found.append((current.lineno, _enclosing_name(enclosing)))
        for child in ast.iter_child_nodes(current):
            walk(child, enclosing)

    for statement in tree.body:
        walk(statement, None)
    return tuple(sorted(set(found)))


def classification_compare_violations(
    items: list[tuple[Path, ast.AST]],
    *,
    display_root: Path,
    exempt: Mapping[tuple[str, str], str] = {},
) -> list[str]:
    """Return ``path:lineno (function)`` strings for non-exempt hand-rolled compares."""
    violations: list[str] = []
    for path, tree in items:
        relative = path.relative_to(display_root).as_posix()
        if relative == _CANONICAL_MODULE:
            continue
        for lineno, function in classification_compare_sites(tree):
            if (relative, function) in exempt:
                continue
            violations.append(f"{relative}:{lineno} (in {function})")
    return violations


def test_no_inline_classification_compare(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Hand-rolled ``.classification`` stored-vs-expected comparisons must be zero.

    All twenty-nine known sites delegate to
    ``inner_envelope_classification_is_expected`` from
    ``cadrumo.adapters.persistence.storage``. Any new inline comparison is a
    regression -- either a re-fragmentation of the check this gate exists to
    prevent, or a genuine peer-coherence variant that belongs in
    ``_CLASSIFICATION_COMPARE_EXEMPTIONS`` with a stated reason.
    """
    items = list(production_ast_items(source_tree_ast))
    violations = classification_compare_violations(
        items,
        display_root=SRC_CADRUMO,
        exempt=_CLASSIFICATION_COMPARE_EXEMPTIONS,
    )
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} hand-rolled .classification comparison(s) found in "
            f"production code:\n  {joined}\n\n"
            "Replace each with inner_envelope_classification_is_expected() from "
            "cadrumo.adapters.persistence.storage. If a site genuinely compares two "
            "classifications with no single 'expected' operand, add it to "
            "_CLASSIFICATION_COMPARE_EXEMPTIONS with a stated reason.",
        )


def test_classification_exemptions_are_all_live(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every exemption must still resolve to a real hand-rolled compare site.

    An exemption whose site has been fixed, deleted, or renamed is a rubber
    stamp waiting to launder the next bad comparison added to that function, so
    a stale key fails here and must be removed.
    """
    live: set[tuple[str, str]] = set()
    for path, tree in production_ast_items(source_tree_ast):
        relative = aeat_relative(path)
        live.update((relative, function) for _, function in classification_compare_sites(tree))

    stale = sorted(key for key in _CLASSIFICATION_COMPARE_EXEMPTIONS if key not in live)
    assert not stale, (
        f"{len(stale)} classification-compare exemption(s) no longer match a real "
        f"site and must be deleted from _CLASSIFICATION_COMPARE_EXEMPTIONS: {stale}"
    )


def test_classification_gate_reds_on_a_planted_bare_compare(tmp_path: Path) -> None:
    """Anti-tautology proof: the gate really fails on every shape it forbids."""
    module = tmp_path / "planted.py"
    module.write_text(
        "\n".join(
            (
                "def not_equal_form(envelope, expected):",
                "    if envelope.classification != expected:",
                "        raise ValueError('mismatch')",
                "",
                "",
                "def is_not_form(envelope, expected):",
                "    if envelope.classification is not expected:",
                "        raise ValueError('mismatch')",
                "",
                "",
                "def reversed_operand_form(envelope, expected):",
                "    if expected is not envelope.classification:",
                "        raise ValueError('mismatch')",
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    violations = classification_compare_violations([(module, tree)], display_root=tmp_path)

    assert violations == [
        "planted.py:2 (in not_equal_form)",
        "planted.py:7 (in is_not_form)",
        "planted.py:12 (in reversed_operand_form)",
    ], violations


def test_classification_gate_permits_the_canonical_predicate_call(tmp_path: Path) -> None:
    """The legal spelling must stay legal, or the gate would force unsafe rewrites."""
    module = tmp_path / "legal.py"
    module.write_text(
        "\n".join(
            (
                "def delegates(envelope, expected):",
                "    if not inner_envelope_classification_is_expected(envelope.classification, expected):",
                "        raise ValueError('mismatch')",
                "",
                "",
                "def unrelated_compare(envelope, expected):",
                "    if envelope.schema_version != expected:",
                "        raise ValueError('mismatch')",
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    assert classification_compare_violations([(module, tree)], display_root=tmp_path) == []


def test_classification_gate_honours_a_function_keyed_exemption(tmp_path: Path) -> None:
    """An exemption suppresses only its own function, never the whole file."""
    module = tmp_path / "mixed.py"
    module.write_text(
        "\n".join(
            (
                "def exempt_site(a, b):",
                "    if a.classification is not b.classification:",
                "        raise ValueError('mismatch')",
                "",
                "",
                "def new_site(envelope, expected):",
                "    if envelope.classification is not expected:",
                "        raise ValueError('mismatch')",
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    violations = classification_compare_violations(
        [(module, tree)],
        display_root=tmp_path,
        exempt={("mixed.py", "exempt_site"): "planted reason"},
    )

    assert violations == ["mixed.py:7 (in new_site)"], violations


__all__ = [
    "classification_compare_sites",
    "classification_compare_violations",
]
