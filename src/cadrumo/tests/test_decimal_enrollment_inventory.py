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

4. ``coerce_decimal(<some string>)`` or ``coerce_decimal_strict(<some string>)``
   anywhere outside the canonical home, unless the site carries a
   ``DECIMAL-TEXT-RATIONALE-*`` declaration saying why its separator convention
   is externally fixed.

Rule 4 exists because rule 3 names ``coerce_decimal`` as an acceptable
destination, and it is acceptable only for machine-produced text. The coercer
reaches ``Decimal(str(value))`` without consulting the ambiguity test, so
``coerce_decimal("1.000")`` is ``Decimal('1.000')`` — one euro from an operator
who typed a thousand. Rewriting a bare ``Decimal(text)`` onto it therefore
satisfies rule 3 while preserving the misread rule 3 exists to stop. Rule 4 asks
about the ARGUMENT rather than the callee, which is why the three correct
machine-numeric coercions in the tree (two float branches and the worksheet
coercer's int/float arm) never appear in its report and need no exemption.

Rule 4's declarations live at the call site rather than in a mapping here, and
that divergence is deliberate: see the module docstring of
:mod:`~tests._decimal_parse_inventory` for the fixture-provenance argument and
for the blind spot a green from rule 4 does NOT cover.

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

from ._decimal_parse_inventory import (
    DECIMAL_TEXT_RATIONALE_MARKER,
    SEPARATOR_SAFE_DESTINATIONS,
    stale_decimal_text_rationale_markers,
    string_parse_decimal_sites,
    string_parse_decimal_violations,
    tolerant_coercion_text_violations,
)
from .inventory import SRC_CADRUMO, aeat_relative, leaf_name, production_ast_items, repo_relative

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_CADRUMO

# Canonical modules exempt from their own rules.
_ROUNDING_MODULE = _SRC_ROOT / "core" / "money" / "__init__.py"
_COERCE_MODULE = _SRC_ROOT / "core" / "decimal" / "_coerce.py"

_CANONICAL_DECIMAL_HOME = _SRC_ROOT / "core" / "decimal"
"""The one home allowed to construct a Decimal from operator-supplied text.

Rule 3 is scoped by CALL SITE, not by layer. It used to name the layers it
governed, and that allowlist is what let the defect through: a bare
``Decimal()`` behind ``--descendiente RENTAS=`` lived in ``domain``, which the
list did not include, so the gate that exists to catch exactly that misread
``12.500`` euros as twelve fifty while staying green.

Widening the list to include ``domain`` would have closed that instance and
left the shape intact, because a layer allowlist encodes an assumption about
where operator input arrives -- and this codebase has an operator-input parser
sitting in ``domain``, which is precisely the assumption being wrong. Scoping
by call site carries no such assumption: parsing text into a Decimal belongs to
the canonical home wherever the caller lives, and everything outside it is in
scope by default rather than by enumeration.
"""

_STRING_PARSE_EXEMPTIONS: Mapping[tuple[str, str], str] = {
    ("application/modelo/calculate_input.py", "_validated_declarante_selector"): (
        "Inverted use: the constructor is a numeric-ness PREDICATE, not a parse. "
        "Success means REFUSE (an amount was typed into a declarante-selector "
        "text casilla). Routing it through the strict grammar would make the "
        "guard more permissive, letting a mis-routed '1e3' past it."
    ),
    ("application/calculations/foreign_asset_redeclaration.py", "_decimal_or_none"): (
        "Modelo 720/721 valuation read, and filing-grade, so the provenance was "
        "traced to both its callers rather than assumed. Neither can carry the "
        "ambiguous shape. The casilla caller reads "
        "revision.input_values_by_casilla_id, whose only non-empty writer is the "
        "calculate replay payload and which stores canonical_decimal_string(...) "
        "output -- that normalises 1E+3 to '1000' and 1.000 to '1', so neither "
        "an exponent nor a thousands-ambiguous spelling can be persisted. The "
        "row caller reads row_binding_values, written by the same serialiser "
        "from Modelo720RowObservation.valuation_amount, a typed non-negative "
        "Decimal. Upstream of both, the CLI boundary already refuses the shape: "
        "try_parse_canonical_decimal returns None for '1.000', '12.500', "
        "'1.234' and '999.999' even with the fraction cap off (measured), "
        "because the ambiguity test is independent of the cap. The external "
        "import path writes an empty dict and contributes nothing."
    ),
    ("application/aggregation/_atribucion_member.py", "_decimal"): (
        "Typed isinstance dispatch over an already-persisted profile fact; the "
        "profile-fact entry boundary owns the text grammar. Reported as a "
        "residual finding rather than tightened here."
    ),
    # --- adapters + core, admitted to scope when rule 3 moved from a layer
    # allowlist to a call-site scope. Every adapter entry below reads
    # machine-produced text, which is the extraction posture, not the strict one.
    ("adapters/inbound/financial/providers/base.py", "parse_amount_value"): (
        "Bank-statement import: the amount comes from a downloaded provider file, not from an operator keystroke."
    ),
    ("adapters/inbound/pdf/label_regex.py", "parse_spanish_decimal"): (
        "PDF label scrape of a printed document; the extraction posture, and "
        "the function is named for the convention it reads."
    ),
    ("adapters/outbound/aeat/sede/_iva_compensation_wallet_parsing.py", "_parse_spanish_decimal"): (
        "Same AEAT sede source as its sibling above."
    ),
    ("adapters/outbound/fx/ecb_provider.py", "_parse_observations"): (
        "ECB reference-rate feed: machine XML from the central bank."
    ),
    ("core/setup_answers.py", "_validate_incn_prior_12_months"): (
        "Inverted use: the constructor is a PARSEABILITY predicate whose result "
        "is discarded -- the answer is stored as text and parsed downstream. "
        "Reported as a residual rather than tightened here, and it is a real "
        "one: it admits the ambiguous 8.000 at the wizard, where the operator "
        "is present to retype, and defers the refusal to the profile fact "
        "carrier, which now leaves it a str and lets the numeric check refuse "
        "with a message about type rather than about notation. INCN feeds the "
        "micro-empresa threshold, so the figure is threshold-bearing."
    ),
    ("core/setup_answers.py", "_validate_objective_estimation_modulos_units"): (
        "Same inverted parseability predicate as its INCN sibling above, on the "
        "modulos unit counts. Reported as a residual on the same terms."
    ),
    # --- domain layer, admitted to scope after the RENTAS=12.500 misread ---
    ("domain/calculations/registry/export_parse.py", "_parse_xml_decimal"): (
        "AEAT-produced export XML, not operator text, and it already normalises "
        "separators explicitly for that machine format."
    ),
    ("domain/calculations/registry/formula_runtime_m100.py", "_m100_eo_agraria_read_indice"): (
        "Reads a registry-authored indice from the compiled snapshot's text "
        "values; the registry TOML is committed data, not typed input."
    ),
    ("domain/calculations/registry/_formula_runtime_m131.py", "_read_modulos_indice"): (
        "Same registry-authored modulos indice as its M100 sibling above."
    ),
    ("domain/calculations/registry/renta_web_open_oracle.py", "_is_non_finite_numeric_text"): (
        "Inverted use: the parse is a non-finiteness PREDICATE over Renta WEB "
        "oracle text. Routing it through the strict grammar would make the "
        "guard more permissive, the same shape as the declarante-selector "
        "exemption above."
    ),
    # --- surfaced when the isinstance-str narrowing reached rule 3. Every one
    # is a pydantic mode="before" validator re-hydrating a Decimal THIS
    # application serialised, so the text is its own canonical dot-decimal
    # output and no separator reading is in question. They are one shape, and
    # they are listed individually rather than as a file-wide waiver so a new
    # bad call in any of these files still fails.
    ("domain/calculations/registry/bindings.py", "_decimal_from_json_string"): (
        "Re-hydrates a casilla observation's Decimal from the JSON this "
        "application wrote; raises RegistryValidationError on a non-numeric."
    ),
    ("domain/iva/schema.py", "_coerce_decimal_field"): (
        "Re-hydrates cash-accounting payment evidence from "
        "Envelope[Transaction].model_validate_json, whose string form this "
        "application serialised."
    ),
    ("domain/transactions/lineage_models.py", "_coerce_inbound"): (
        "Same JSON re-hydration for the classification confidence and "
        "business_pct fields, from the app's own persisted envelope."
    ),
    ("domain/transactions/models.py", "_coerce_decimal_field"): (
        "Same JSON re-hydration as its _coerce_inbound sibling above, on the model's own Decimal fields."
    ),
    ("domain/deadlines/profiles.py", "_parse_decimal"): (
        "Reads canonical profile facts already persisted, so the text grammar "
        "belongs to the profile write boundary rather than here. Reported as a "
        "residual finding rather than tightened: the profile fact carrier "
        "promotes an operator string to Decimal before this is reached, and "
        "the grammar has to be enforced where the string is still a string."
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
    """Return ``(path, AST)`` pairs for every production file outside the canonical home."""
    return tuple(
        (path, tree)
        for path, tree in production_ast_items(source_tree_ast)
        if not path.is_relative_to(_CANONICAL_DECIMAL_HOME)
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


def _destination_scan_items(
    source_tree_ast: Mapping[Path, ast.AST],
) -> tuple[tuple[Path, ast.AST, list[str]], ...]:
    """Return ``(path, AST, source lines)`` for every production file outside the canonical home.

    A file that has vanished since the session-scoped AST cache was built is
    skipped rather than raising. Rule 4 needs the raw source lines (the
    declaration is a comment, which the AST discards), so unlike its rule-3
    sibling it re-reads from disk — and this tree has many agents working in it
    at once, so a scratch module can appear and be deleted between the cache
    build and the read. That really happened on this gate's first full run,
    against ``domain/_scope_widening_probe.py``.

    Skipping is correct rather than merely convenient: the question asked is
    whether a live production file carries an undeclared coercion, and a path
    with no file behind it has no live site and no declaration to go stale. The
    cache entry, not the tree, is what is out of date.
    """
    items: list[tuple[Path, ast.AST, list[str]]] = []
    for path, tree in _string_parse_scan_items(source_tree_ast):
        try:
            source = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        items.append((path, tree, source.splitlines()))
    return tuple(items)


def _planted(tmp_path: Path, name: str, *lines: str) -> tuple[Path, ast.AST, list[str]]:
    """Write a synthetic module and return it as a scan item.

    Synthetic sources are scanned through an injected ``display_root``, so no
    proof in this module monkeypatches the production scan surface or commits a
    violation to the tree.
    """
    module = tmp_path / name
    module.write_text("\n".join((*lines, "")), encoding="utf-8")
    source = module.read_text(encoding="utf-8")
    return module, ast.parse(source), source.splitlines()


_IMPORT_COERCERS = "from cadrumo.core.decimal import coerce_decimal, coerce_decimal_strict"


def test_no_undeclared_tolerant_coercion_of_text(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Text reaching a tolerant coercer must carry a declaration at the site.

    The coercer resolves the ambiguous Spanish thousands shape instead of
    refusing it, so a site that admits operator text must either move to one of
    the separator-safe destinations or state why its separator convention is
    fixed by something other than the writer's locale.
    """
    violations = tolerant_coercion_text_violations(
        _destination_scan_items(source_tree_ast),
        display_root=_SRC_ROOT,
    )
    if violations:
        joined = "\n  ".join(violations)
        safe = ", ".join(SEPARATOR_SAFE_DESTINATIONS)
        raise AssertionError(
            f"{len(violations)} tolerant Decimal coercion(s) of provably-string text:\n  {joined}\n\n"
            f"coerce_decimal('1.000') is Decimal('1.000') -- one euro from an operator who meant a "
            f"thousand. Route the text to one of {safe}, or add a "
            f"'# {DECIMAL_TEXT_RATIONALE_MARKER}<SLUG>: ...' comment on the call line or in the "
            "comment block immediately above it, saying why the separator convention is fixed by "
            "the source rather than chosen by whoever wrote the value.",
        )


def test_decimal_text_rationale_declarations_are_all_live(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every declaration must sit beside a site the detector really reports.

    This is the cross-check that keeps an at-the-site declaration from decaying
    into the path-keyed allowlist it replaces. A marker left behind by a fixed
    or deleted call is a rubber stamp waiting to launder the next coercion added
    beneath it, and unlike a mapping entry it is invisible to a reader who is
    not already looking at that line.
    """
    stale = stale_decimal_text_rationale_markers(
        _destination_scan_items(source_tree_ast),
        display_root=_SRC_ROOT,
    )
    assert not stale, (
        f"{len(stale)} {DECIMAL_TEXT_RATIONALE_MARKER}* declaration(s) govern no reported coercion "
        f"and must be deleted:\n  " + "\n  ".join(stale)
    )


def test_destination_gate_reds_on_an_undeclared_text_coercion(tmp_path: Path) -> None:
    """Anti-tautology proof: the shape rule 3 would bless must fail rule 4.

    The planted module is exactly the rewrite that satisfies rule 3 — the bare
    ``Decimal(raw)`` moved onto the tolerant coercer — so a green here would
    mean the two rules together still permit the defect they were built for.
    """
    item = _planted(
        tmp_path,
        "planted.py",
        _IMPORT_COERCERS,
        "",
        "",
        "def rewritten_to_satisfy_rule_three(raw: str):",
        "    return coerce_decimal(raw)",
        "",
        "",
        "def strict_variant(raw: str):",
        "    return coerce_decimal_strict(raw.strip())",
    )

    violations = tolerant_coercion_text_violations((item,), display_root=tmp_path)

    assert violations == [
        "planted.py:5 (in rewritten_to_satisfy_rule_three, coerce_decimal)",
        "planted.py:9 (in strict_variant, coerce_decimal_strict)",
    ], violations


def test_destination_gate_ignores_provably_numeric_arguments(tmp_path: Path) -> None:
    """The three correct machine-numeric coercions must not be reported.

    A per-symbol sweep for ``coerce_decimal`` calls all three violations — a 43%
    false-positive rate against the hand-classified set, which is the rate at
    which a detector stops being read and starts accumulating exemptions. Keying
    on the argument's provable type drops them by construction, so this is the
    control that the gate is not merely loud.
    """
    item = _planted(
        tmp_path,
        "numeric.py",
        _IMPORT_COERCERS,
        "from decimal import Decimal",
        "",
        "",
        "def float_branch(value: object):",
        "    if isinstance(value, float):",
        "        return coerce_decimal(value)",
        "    return None",
        "",
        "",
        "def already_decimal(value: Decimal):",
        "    return coerce_decimal(value)",
        "",
        "",
        "def counts(rows: list[int]):",
        "    return coerce_decimal(len(rows))",
    )

    assert tolerant_coercion_text_violations((item,), display_root=tmp_path) == []


def test_destination_gate_sees_an_isinstance_narrowed_branch(tmp_path: Path) -> None:
    """A ``str`` branch of an isinstance dispatch is text, and its siblings are not.

    This is the shape the worksheet coercer uses, and without the narrowing the
    gate would report neither arm — reading as clean for the wrong reason.
    """
    item = _planted(
        tmp_path,
        "dispatch.py",
        _IMPORT_COERCERS,
        "",
        "",
        "def dispatch(raw: object):",
        "    if isinstance(raw, (int, float)):",
        "        return coerce_decimal(raw)",
        "    if isinstance(raw, str):",
        "        return coerce_decimal(raw)",
        "    return None",
    )

    violations = tolerant_coercion_text_violations((item,), display_root=tmp_path)

    assert violations == ["dispatch.py:8 (in dispatch, coerce_decimal)"], violations


def test_destination_gate_resolves_an_aliased_coercer_import(tmp_path: Path) -> None:
    """A renamed import must not hide the call.

    The tree really does alias one of these (``coerce_decimal_strict as
    _coerce_decimal_strict``), and the sibling cast ratchet documents
    spelling-matched detection failing on exactly this shape.
    """
    item = _planted(
        tmp_path,
        "aliased.py",
        "from cadrumo.core.decimal import coerce_decimal as _money",
        "",
        "",
        "def parses(raw: str):",
        "    return _money(raw)",
    )

    violations = tolerant_coercion_text_violations((item,), display_root=tmp_path)

    assert violations == ["aliased.py:5 (in parses, coerce_decimal)"], violations


def test_a_declaration_clears_only_its_own_site(tmp_path: Path) -> None:
    """A declaration governs the call it sits beside, never the file or the function."""
    item = _planted(
        tmp_path,
        "mixed.py",
        _IMPORT_COERCERS,
        "",
        "",
        "def two_calls(raw: str, other: str):",
        f"    # {DECIMAL_TEXT_RATIONALE_MARKER}PLANTED: machine-produced, separator fixed.",
        "    first = coerce_decimal(raw)",
        "    second = coerce_decimal(other)",
        "    return first, second",
    )

    violations = tolerant_coercion_text_violations((item,), display_root=tmp_path)

    assert violations == ["mixed.py:7 (in two_calls, coerce_decimal)"], violations
    assert stale_decimal_text_rationale_markers((item,), display_root=tmp_path) == []


def test_a_declaration_left_behind_by_a_fixed_site_is_reported(tmp_path: Path) -> None:
    """Removing the coercion but leaving its declaration must fail.

    Without this the at-the-site scheme is strictly worse than a mapping: an
    orphaned marker sits invisibly above whatever line is written next.
    """
    item = _planted(
        tmp_path,
        "orphaned.py",
        "from cadrumo.core.decimal import try_parse_canonical_decimal",
        "",
        "",
        "def now_safe(raw: str):",
        f"    # {DECIMAL_TEXT_RATIONALE_MARKER}PLANTED: reason for a call that no longer exists.",
        "    return try_parse_canonical_decimal(raw)",
    )

    assert stale_decimal_text_rationale_markers((item,), display_root=tmp_path) == ["orphaned.py:5"]


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


def test_string_parse_gate_sees_an_isinstance_narrowed_branch(tmp_path: Path) -> None:
    """Rule 3 must read an ``isinstance``-narrowed ``str`` branch as text.

    Rule 4 consumed this narrowing one change before rule 3 did, so without a
    proof pinning it here the two could silently diverge again on what counts as
    text — and reverting the one-token flip in ``_visit_scope`` would take rule 3
    back to reporting neither arm of an isinstance dispatch.
    """
    module = tmp_path / "narrowed.py"
    module.write_text(
        "\n".join(
            (
                "from decimal import Decimal",
                "",
                "",
                "def dispatch(raw: object) -> Decimal | None:",
                "    if isinstance(raw, (int, float)):",
                "        return Decimal(raw)",
                "    if isinstance(raw, str):",
                "        return Decimal(raw)",
                "    return None",
                "",
            ),
        ),
        encoding="utf-8",
    )
    tree = ast.parse(module.read_text(encoding="utf-8"))

    violations = string_parse_decimal_violations(((module, tree),), display_root=tmp_path)

    assert violations == ["narrowed.py:8 (in dispatch)"], violations


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
