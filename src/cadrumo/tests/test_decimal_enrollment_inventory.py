"""Inventory gate for canonical Decimal rounding, coercion, and text parsing.

Production modules under ``src/cadrumo/`` must not use:

1. ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` inline.
   All callers must delegate to :func:`~core.money.round_to_cents`.

2. ``Decimal(str(`` bare coercion patterns inline.
   All callers must delegate to :func:`~core.decimal.coerce_decimal`.

3. ``Decimal(<some string>)`` anywhere in ``entrypoints/`` or ``application/``.
   All callers must delegate to :func:`~core.decimal.try_parse_canonical_decimal`
   (operator-typed text) or :func:`~core.decimal.coerce_decimal` (machine-produced
   text), outside the reasoned exemptions declared below.

Rule 3 exists because rule 2 was structurally blind to the shape that actually
ships defects. ``_is_decimal_str_call`` requires the single argument to be a
literal ``str(...)`` *call*, so ``Decimal(str(x))`` was caught while
``Decimal(x)`` — where ``x`` is already a string — was invisible. That is the same
inversion this file's own rule 1 documents for ``quantize``: the gate forbade the
safe spelling and permitted the dangerous one. Five operator-typed money
boundaries parsed with a bare ``Decimal(...)`` while this module reported green.

The only production exclusions from rules 1 and 2 are the canonical
implementation modules themselves. Test modules may exercise decimal behaviour
directly.

See Also:
    :mod:`~core.money`
        Canonical euro-cent quantum and half-up rounding helper.
    :mod:`~core.decimal`
        Canonical Decimal coercion, grammar, and formatting helpers.
    :mod:`~tests._inventory`
        Shared production AST inventory surface used by this ratchet.
    :mod:`~tests._decimal_parse_inventory`
        String-argument detection that backs rule 3.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ._decimal_parse_inventory import string_parse_decimal_sites, string_parse_decimal_violations
from ._inventory import SRC_CADRUMO, aeat_relative, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_CADRUMO

# Canonical modules exempt from their own rules.
_ROUNDING_MODULE = _SRC_ROOT / "core" / "money" / "__init__.py"
_COERCE_MODULE = _SRC_ROOT / "core" / "decimal" / "_coerce.py"

_STRING_PARSE_LAYERS: tuple[str, ...] = ("entrypoints", "application")
"""Layers rule 3 governs: the operator-facing boundary and the services behind it."""

_STRING_PARSE_EXEMPTIONS: Mapping[tuple[str, str], str] = {
    ("application/modelo/_decimal_parsing.py", "decimal_from_string"): (
        "Canonical implementation. This module is the owning home for the "
        "string-to-Decimal parse of AEAT-produced borrador snapshot values, the "
        "same category of exemption core/decimal/_coerce.py carries."
    ),
    ("application/modelo/_calculate_input.py", "_validated_declarante_selector"): (
        "Inverted use: the constructor is a numeric-ness PREDICATE, not a parse. "
        "Success means REFUSE (an amount was typed into a declarante-selector "
        "text casilla). Routing it through the strict grammar would make the "
        "guard more permissive, letting a mis-routed '1e3' past it."
    ),
    ("application/ledger/_evidence_advisory.py", "_parse_amount"): (
        "Deliberately tolerant OCR scrape of printed invoice text, with explicit "
        "Spanish-separator normalisation; returns None on failure and feeds only "
        "a non-blocking advisory. The tolerant coerce posture, not the strict one."
    ),
    ("application/ledger/_evidence_draft.py", "_parse_labelled_amount"): (
        "Consumes normalize_decimal_separators output — already the canonical "
        "tolerant helper for machine-produced evidence text."
    ),
    ("application/ledger/_evidence_draft.py", "_find_iva_rate"): (
        "Deliberately tolerant OCR rate scrape; returns None on failure. Same "
        "machine-produced-text posture as _parse_labelled_amount above."
    ),
    ("application/invoices/_bulk_import.py", "_parse_row_decimal"): (
        "CSV bulk-import transport, not a hand-typed boundary: already carries an "
        "is_finite() guard and a typed per-row refusal naming row and field."
    ),
    ("application/modelo/_local_observation_spreadsheet.py", "parse_casilla_value_spreadsheet"): (
        "Spreadsheet transport with deliberate European-separator tolerance "
        "(comma to dot); a strict grammar here would refuse the very files this "
        "reader exists to accept."
    ),
    ("application/aggregation/_atribucion_member.py", "_decimal"): (
        "Typed isinstance dispatch over an already-persisted profile fact; the "
        "profile-fact entry boundary owns the text grammar. Reported as a "
        "residual finding rather than tightened here."
    ),
    ("application/modelo/_iva_wallet_gate.py", "_decision_has_concrete_zero_authority"): (
        "Compares app-persisted wallet decision amounts the write boundary "
        "already validated; no operator text crosses this call."
    ),
    ("application/modelo/_iva_wallet_gate.py", "_calculated_revision_local_iva_compensation_recurrence"): (
        "Reads a persisted casilla_values entry the calculate boundary already validated through the canonical grammar."
    ),
}
"""Reasoned exemptions from rule 3, keyed by ``(path, enclosing function)``.

Keyed by function rather than line number so an unrelated edit in the same file
cannot silently slide a site out of its exemption, and so a *new* bad call in an
already-exempt file still fails. Every key is proven to still resolve to a real
site by :func:`test_string_parse_exemptions_are_all_live`, so a fixed site's
exemption cannot rot into a rubber stamp.
"""


def _is_excluded(path: Path) -> bool:
    return path in (_ROUNDING_MODULE, _COERCE_MODULE)


def _string_parse_scan_items(
    source_tree_ast: Mapping[Path, ast.AST],
) -> tuple[tuple[Path, ast.AST], ...]:
    """Return ``(path, AST)`` pairs for production files in the governed layers."""
    return tuple(
        (path, tree)
        for path, tree in production_ast_items(source_tree_ast)
        if path.relative_to(_SRC_ROOT).parts[0] in _STRING_PARSE_LAYERS
    )


def _is_decimal_literal_call(node: ast.AST, literal: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and leaf_name(node.func) == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == literal
    )


def _is_round_half_up_keyword(keyword: ast.keyword) -> bool:
    return keyword.arg == "rounding" and leaf_name(keyword.value) == "ROUND_HALF_UP"


def _is_cent_quantize_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "quantize"
        and len(node.args) >= 1
        and _is_decimal_literal_call(node.args[0], "0.01")
        and any(_is_round_half_up_keyword(keyword) for keyword in node.keywords)
    )


def _is_decimal_str_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and leaf_name(node.func) == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Call)
        and leaf_name(node.args[0].func) == "str"
    )


def _collect_quantize_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline quantize call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for node in ast.walk(tree):
            if _is_cent_quantize_call(node):
                assert isinstance(node, ast.Call)
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    return violations


def _collect_decimal_str_violations(source_tree_ast: Mapping[Path, ast.AST]) -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every bare Decimal(str()) call."""
    violations: list[str] = []
    for path, tree in production_ast_items(source_tree_ast):
        if _is_excluded(path):
            continue
        for node in ast.walk(tree):
            if _is_decimal_str_call(node):
                assert isinstance(node, ast.Call)
                violations.append(f"{repo_relative(path)}:{node.lineno}")
    return violations


def test_no_inline_quantize_round_half_up(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Inline ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` must be zero.

    All known sites use ``round_to_cents`` from ``cadrumo.core.money``.
    Any new inline call is a regression.
    """
    violations = _collect_quantize_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)"
            f" call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with round_to_cents() from cadrumo.core.money.",
        )


def test_no_bare_decimal_str_coercion(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Bare ``Decimal(str(`` coercion must be zero in production code.

    All call-sites must delegate to :func:`~core.decimal.coerce_decimal`.
    The only permitted occurrence lives in the canonical helper module itself,
    which is excluded above.
    """
    violations = _collect_decimal_str_violations(source_tree_ast)
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare Decimal(str()) coercion call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with coerce_decimal() from cadrumo.core.decimal.",
        )


def test_no_unvalidated_string_to_decimal_parse(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """``Decimal(<some string>)`` must be zero in ``entrypoints/`` and ``application/``.

    An integer argument (``Decimal(len(rows))``, ``Decimal(self.runs)``) is never
    reported: no grammar is involved, so nothing can misparse. Only a provably
    string-typed argument is, because only text carries a grammar — and a bare
    constructor admits scientific notation, a leading ``+``, an underscore digit
    separator, and the non-finite ``NaN``/``Infinity``, whose ``False``-to-
    everything comparisons silently defeat any ``> 0`` under-declaration guard.
    """
    violations = string_parse_decimal_violations(
        _string_parse_scan_items(source_tree_ast),
        display_root=_SRC_ROOT,
        exempt=_STRING_PARSE_EXEMPTIONS,
    )
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} unvalidated string-to-Decimal parse(s) found in "
            f"entrypoints/ or application/:\n  {joined}\n\n"
            "Route operator-typed text through try_parse_canonical_decimal() and "
            "machine-produced text through coerce_decimal(), both from "
            "cadrumo.core.decimal. If a site genuinely cannot use either, add it to "
            "_STRING_PARSE_EXEMPTIONS with a stated reason.",
        )


def test_string_parse_exemptions_are_all_live(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every rule-3 exemption must still resolve to a real site.

    An exemption whose site has been fixed or deleted is a rubber stamp waiting
    to launder the next call added to that function, so a stale key fails here
    and must be removed.
    """
    live: set[tuple[str, str]] = set()
    for path, tree in _string_parse_scan_items(source_tree_ast):
        relative = aeat_relative(path)
        live.update((relative, function) for _, function in string_parse_decimal_sites(tree))

    stale = sorted(key for key in _STRING_PARSE_EXEMPTIONS if key not in live)
    assert not stale, (
        f"{len(stale)} rule-3 exemption(s) no longer match a real site and must be "
        f"deleted from _STRING_PARSE_EXEMPTIONS: {stale}"
    )


def test_string_parse_gate_reds_on_a_planted_bare_call(tmp_path: Path) -> None:
    """Anti-tautology proof: the gate really fails on the shape it forbids.

    The predecessor rule reported green over five live defects, so a demonstrated
    failure mode is the only evidence this gate is worth anything. A synthetic
    module is scanned through an injected ``display_root`` — no monkeypatching of
    the production scan surface — and must yield exactly the bare string parse.
    """
    module = tmp_path / "planted.py"
    module.write_text(
        "\n".join(
            (
                "from decimal import Decimal",
                "",
                "",
                "def parses_operator_text(raw: str) -> Decimal:",
                "    return Decimal(raw)",
                "",
                "",
                "def parses_via_a_local(raw: str) -> Decimal:",
                "    text = raw.strip()",
                "    return Decimal(text)",
                "",
                "",
                "def widens_an_integer(rows: list[int]) -> Decimal:",
                "    return Decimal(len(rows))",
                "",
                "",
                "def uses_a_literal() -> Decimal:",
                '    return Decimal("1.00")',
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    violations = string_parse_decimal_violations(((module, tree),), display_root=tmp_path)

    assert violations == ["planted.py:5 (in parses_operator_text)", "planted.py:10 (in parses_via_a_local)"], violations


def test_string_parse_gate_permits_literals_and_integer_widening(tmp_path: Path) -> None:
    """The legal spellings must stay legal, or the gate would force unsafe rewrites.

    Paired with the planted-failure proof above: a gate that reds on everything is
    as useless as one that reds on nothing.
    """
    module = tmp_path / "legal.py"
    module.write_text(
        "\n".join(
            (
                "from decimal import Decimal",
                "",
                "CENT = Decimal('0.01')",
                "",
                "",
                "def widen(count: int, ratio: float) -> tuple[Decimal, Decimal, Decimal]:",
                "    return Decimal(count), Decimal(ratio), Decimal(len('abc'))",
                "",
                "",
                "def delegates(raw: str) -> Decimal | None:",
                "    from cadrumo.core.decimal import try_parse_canonical_decimal",
                "",
                "    return try_parse_canonical_decimal(raw)",
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    assert string_parse_decimal_violations(((module, tree),), display_root=tmp_path) == []


def test_string_parse_gate_honours_a_function_keyed_exemption(tmp_path: Path) -> None:
    """An exemption suppresses only its own function, never the whole file."""
    module = tmp_path / "mixed.py"
    module.write_text(
        "\n".join(
            (
                "from decimal import Decimal",
                "",
                "",
                "def exempt_site(raw: str) -> Decimal:",
                "    return Decimal(raw)",
                "",
                "",
                "def new_site(raw: str) -> Decimal:",
                "    return Decimal(raw)",
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    violations = string_parse_decimal_violations(
        ((module, tree),),
        display_root=tmp_path,
        exempt={("mixed.py", "exempt_site"): "planted reason"},
    )

    assert violations == ["mixed.py:9 (in new_site)"], violations
