"""Ratchet: per-modelo tokens in generic application modules only decrease.

The architecture
review found per-modelo special cases accreting inside generic application
modules — modelo-branched logic keyed on ``Modelo.M###`` members or on
``_M###_*`` module constants — where dedicated per-modelo homes
(``_m303_m349_reconcile.py``, ``_m036_lifecycle.py``, ``_iva_wallet_gate.py``)
prove the codebase already knows the right shape.

This AST gate inventories those per-modelo tokens across a NAMED list of generic
modules and records a per-module baseline set. The set may only SHRINK: a new
``Modelo.M###`` branch or ``_M###_*`` constant in one of these modules creates an
unexpected token and fails the gate, unless the baseline is CONSCIOUSLY changed
in the same review — so a new per-modelo carve-out in a generic module is a
deliberate, reviewed act, not an accident.

Distinct tokens are compared as a named set (not raw occurrences) so the gate is
stable under refactors that merely add or remove a use of an existing token, but
still catches swaps where one per-modelo symbol disappears and another appears.

Scope, measured (this is an enrolment ratchet, not a tree-wide sweep): the gate
binds the three modules named in ``_RATCHET_BASELINE`` and says nothing about any
other module. A sweep of ``application/`` on 2026-08-03 found roughly 54 further
generic modules carrying per-modelo tokens outside the ratchet. That number is
NOT a defect count — an unknown share of it is legitimately out of scope by the
rules below (dedicated per-modelo homes such as ``_iva_wallet_gate.py``, cited
above as the right shape, and modelo-KEYED DATA modules), and separating the two
needs a per-module judgement that only a reviewer can make. Read a green run as
"the three enrolled modules have not accreted", never as "generic modules are
free of per-modelo branching".

Scope note (no silent caps): the domain formula runtime
(``domain/calculations/registry/formula_runtime.py``) is deliberately NOT in
this list. Its per-modelo *op evaluators* (``_evaluate_m100_*`` /
``_evaluate_m210_*`` / ``_evaluate_m131_*``) are named per-modelo behaviour that
is permitted, and the module is an actively-churned dispatch surface; ratcheting
it is deferred to a follow-up once its dispatch shape stabilises. Modelo-KEYED
DATA modules (applicability rules, censo modelo sets, query projections) are out
of scope by design — only modelo-BRANCHED LOGIC in generic modules is the debt.

See Also:
    :mod:`~tests._inventory`
        Provides the production AST inventory and repository-relative path
        helpers used by this ratchet.
    :class:`~core.Modelo`
        Closed modelo identifier enum whose ``M###`` members are detected when
        they appear in generic application logic.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from pathlib import Path
from typing import TypeGuard

import pytest

from .inventory import aeat_relative, production_ast_items

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ``_M###_<NAME>`` module constants (e.g. _M100_CUOTA_INTEGRA_ESTATAL_CASILLA).
_NAME_TOKEN_RE = re.compile(r"^_M\d+_")
# ``M###`` attribute of the core ``Modelo`` enum (e.g. Modelo.M303).
_MODELO_ATTR_RE = re.compile(r"^M\d+$")

#: The named generic application modules under ratchet, mapped to the exact
#: per-modelo-token baseline recorded after the architecture-remediation sweep.
#: The set for each module may only shrink. Adding a token to a baseline is a
#: conscious, reviewed decision (a new per-modelo carve-out) - never an accident.
_RATCHET_BASELINE: dict[str, frozenset[str]] = {
    "application/modelo/projection.py": frozenset(
        {
            "Modelo.M100",
            "Modelo.M130",
            "_M100_BASE_LIQUIDABLE_GENERAL_CASILLA",
            "_M100_CUOTA_INTEGRA_AUTONOMICA_CASILLA",
            "_M100_CUOTA_INTEGRA_ESTATAL_CASILLA",
            "_M100_CUOTA_LIQUIDA_AUTONOMICA_CASILLA",
            "_M100_CUOTA_LIQUIDA_ESTATAL_CASILLA",
            "_M100_CUOTA_RESULTANTE_CASILLA",
            "_M100_PAGOS_FRACCIONADOS_CASILLA",
            "_M100_RENDIMIENTO_NETO_PROJECTED_CASILLA",
            "_M130_GASTOS_CASILLA",
            "_M130_INGRESOS_CASILLA",
            "_M130_RENDIMIENTO_NETO_CASILLA",
            "_M130_RESULTADO_FINAL_CASILLA",
        }
    ),
    # Modelo.M210 gates the live M210 IRNR gross-income source-mode carve-out
    # (`_m210_gross_source_mode`), enrolled with the live IRNR income-ledger
    # resolver in the calculate mesh. A conscious, reviewed addition for a
    # shipped resolver, not an accidental accretion.
    "application/modelo/calculation_actions.py": frozenset({"Modelo.M210"}),
    "application/modelo/_verification_cross_period.py": frozenset(
        {
            "Modelo.M202",
            "Modelo.M303",
            "_M100_ZERO_BIN_LEGAL_REFS",
            "_M100_ZERO_VALUE_PREVIOUS_FILING_BINDING_RE",
            "_M111_NO_RETENCIONES_LEGAL_REFS",
            "_M202_FIRST_YEAR_LEGAL_REFS",
        }
    ),
}


def _modelo_binding_names(tree: ast.AST) -> set[str]:
    """Return every local name bound to the core ``Modelo`` enum in ``tree``.

    A module may import the enum under an alias (``from ...core import Modelo as
    _Modelo``), and four production modules do. Matching the literal name
    ``Modelo`` alone made every ``_Modelo.M###`` reference invisible, so a module
    using the alias would inventory as carrying zero per-modelo tokens and pass
    this ratchet no matter how many carve-outs it held.
    """
    names = {"Modelo"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names.update(alias.asname for alias in node.names if alias.name == "Modelo" and alias.asname)
    return names


def _per_modelo_tokens(tree: ast.AST) -> set[str]:
    """Return the distinct per-modelo tokens referenced in ``tree``.

    A token is either a ``_M###_*`` bare name or an ``M###`` attribute access on
    whatever local name the module bound the core ``Modelo`` enum to. Tokens are
    reported under the canonical ``Modelo.M###`` spelling regardless of the local
    alias, so a baseline stays readable and an alias rename cannot silently
    rewrite it. Comments and string literals are ignored (the AST carries neither
    as identifiers), so only real code references count.
    """
    binding_names = _modelo_binding_names(tree)
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _NAME_TOKEN_RE.match(node.id):
            tokens.add(node.id)
        elif (
            isinstance(node, ast.Attribute)
            and _MODELO_ATTR_RE.match(node.attr)
            and isinstance(node.value, ast.Name)
            and node.value.id in binding_names
        ):
            tokens.add(f"Modelo.{node.attr}")
    return tokens


def test_per_modelo_token_set_does_not_exceed_baseline(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Each named generic module carries only previously reviewed per-modelo tokens."""
    inventory = {aeat_relative(path): tree for path, tree in production_ast_items(source_tree_ast)}
    assert _RATCHET_BASELINE, "the ratchet baseline is empty; no named module can exceed a baseline that lists none"
    violations: list[str] = []
    for relative_path, baseline in sorted(_RATCHET_BASELINE.items()):
        tree = inventory.get(relative_path)
        if tree is None:
            violations.append(f"named ratchet module missing: {relative_path}")
            continue
        tokens = _per_modelo_tokens(tree)
        unexpected = tokens - baseline
        if unexpected:
            violations.append(
                f"{relative_path} now references unexpected per-modelo token(s): {sorted(unexpected)}. "
                f"The reviewed baseline is {sorted(baseline)}. A new per-modelo carve-out in a generic "
                "module must move to a named `_m<id>_*` module or registry data; if this is a "
                "conscious, reviewed addition, update the named baseline in the same commit.",
            )

    assert not violations, "\n".join(violations)


def test_no_baseline_entry_has_gone_stale(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Every baseline token must still be referenced by the module that declares it.

    The module docstring promises the recorded set "may only SHRINK", but the
    inventory check above compares ``tokens - baseline`` and so only ever refuses
    an ADDITION. Nothing made the baseline actually shrink when a carve-out was
    removed, and a baseline entry left behind is not inert: it is a standing
    pre-authorisation for that exact token to reappear in that module, silently
    and without the reviewed decision the ratchet exists to force.

    This closes the promised direction, so the set is now genuinely monotonic.
    """
    inventory = {aeat_relative(path): tree for path, tree in production_ast_items(source_tree_ast)}
    stale: list[str] = []
    for relative_path, baseline in sorted(_RATCHET_BASELINE.items()):
        tree = inventory.get(relative_path)
        if tree is None:
            continue
        vanished = sorted(baseline - _per_modelo_tokens(tree))
        if vanished:
            stale.append(f"{relative_path}: {vanished}")

    assert not stale, (
        "baseline token(s) no longer referenced by their module:\n  "
        + "\n  ".join(stale)
        + "\n\nRemove them from _RATCHET_BASELINE in this commit. A retired carve-out "
        "that stays listed silently re-authorises its own return."
    )


def _unmatchable_modelo_references(tree: ast.AST) -> list[str]:
    """Return references to a ``Modelo`` member that :func:`_per_modelo_tokens` cannot see.

    The matcher recognises exactly one route to a member: an ``M###`` attribute
    whose receiver is a bare name bound to the enum by an ``ImportFrom``. Python
    offers several other routes to the same member, and each is invisible to it:

    * ``_M = Modelo`` then ``_M.M303`` — rebinding by ASSIGNMENT rather than by
      import alias, which :func:`_modelo_binding_names` does not track.
    * ``core.Modelo.M303`` — a dotted receiver, so ``node.value`` is an
      ``ast.Attribute`` where the matcher requires an ``ast.Name``.
    * ``Modelo["M303"]`` and ``getattr(Modelo, "M303")`` — lookups by member
      name, which produce no ``M###`` attribute node at all.

    None of these appear anywhere in the production tree today, which is exactly
    why this is a precondition guard rather than a test pinning the blindness.
    Pinning it would fail the day someone repaired the matcher, which is
    backwards; this fires the day the gap first costs something — the day one of
    these spellings enters a module under ratchet, where it would otherwise
    inventory as zero tokens and pass while holding a real carve-out.
    """
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name) and node.value.id == "Modelo":
            targets = ", ".join(t.id for t in node.targets if isinstance(t, ast.Name))
            if targets:
                offenders.append(f"line {node.lineno}: `{targets} = Modelo` rebinds the enum by assignment")
        elif isinstance(node, ast.Attribute) and _MODELO_ATTR_RE.match(node.attr):
            if isinstance(node.value, ast.Attribute) and node.value.attr == "Modelo":
                offenders.append(
                    f"line {node.lineno}: `{ast.unparse(node)}` reaches the enum through a dotted receiver"
                )
        elif _is_modelo_lookup_by_member_name(node):
            offenders.append(f"line {node.lineno}: `{ast.unparse(node)}` looks the member up by name")
    return offenders


def _is_modelo_lookup_by_member_name(node: ast.AST) -> TypeGuard[ast.expr]:
    """Return whether *node* reaches a ``Modelo`` member by its NAME rather than as an attribute.

    ``Modelo["M303"]`` and ``getattr(Modelo, "M303")`` are the same move spelled
    two ways, and neither produces an ``M###`` attribute node for the matcher to
    find. ``Modelo("303")`` is deliberately excluded: hydrating a member from its
    stored registry VALUE is the loader boundary's canonical call and must stay
    free.
    """
    if isinstance(node, ast.Subscript):
        return isinstance(node.value, ast.Name) and node.value.id == "Modelo"
    if isinstance(node, ast.Call):
        return (
            isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and bool(node.args)
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "Modelo"
        )
    return False


def test_ratcheted_modules_spell_modelo_the_one_way_the_matcher_sees(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """No module under ratchet may reach a ``Modelo`` member by an unmatchable route.

    The ratchet's guarantee is only as wide as its matcher. A carve-out spelled
    any of the ways :func:`_unmatchable_modelo_references` describes would leave
    the module inventorying as carrying zero per-modelo tokens, so the baseline
    comparison would pass no matter how many carve-outs it held — the same
    failure the aliased-import case caused before it was fixed, reached through a
    different door.
    """
    inventory = {aeat_relative(path): tree for path, tree in production_ast_items(source_tree_ast)}
    violations: list[str] = []
    for relative_path in sorted(_RATCHET_BASELINE):
        tree = inventory.get(relative_path)
        if tree is None:
            continue
        violations.extend(f"{relative_path} {offence}" for offence in _unmatchable_modelo_references(tree))

    assert not violations, (
        "module(s) under ratchet reach the Modelo enum by a route the ratchet's matcher cannot see:\n  "
        + "\n  ".join(violations)
        + "\n\nSpell it `from ...core import Modelo` (optionally aliased) and use a bare "
        "`Modelo.M###` attribute, or teach _per_modelo_tokens the new route in this commit."
    )


def _tokens_of(source: str) -> set[str]:
    """Return the per-modelo tokens the live matcher finds in *source*."""
    return _per_modelo_tokens(ast.parse(source))


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        pytest.param("x = Modelo.M303\n", {"Modelo.M303"}, id="direct-enum-attribute"),
        pytest.param(
            "from ...core import Modelo as _Modelo\nx = _Modelo.M303\n",
            {"Modelo.M303"},
            id="aliased-enum-import",
        ),
        pytest.param(
            "from ...core import Modelo as _M\nx = _M.M100.value\n",
            {"Modelo.M100"},
            id="aliased-enum-value-access",
        ),
        pytest.param("x = _M100_CUOTA_CASILLA\n", {"_M100_CUOTA_CASILLA"}, id="module-constant"),
        pytest.param(
            "if modelo == Modelo.M130:\n    x = _M130_INGRESOS_CASILLA\n",
            {"Modelo.M130", "_M130_INGRESOS_CASILLA"},
            id="branch-plus-constant",
        ),
    ),
)
def test_matcher_sees_every_per_modelo_token_spelling(source: str, expected: set[str]) -> None:
    """Anti-tautology proof: each token spelling is planted and must be inventoried.

    The aliased cases were unreachable before this proof existed. Four production
    modules import the enum as ``_Modelo``, so any of them enrolled in the
    baseline would have inventoried as carrying zero tokens and passed the
    ratchet while holding real carve-outs. Sources are parsed in memory; nothing
    is committed to the tree.
    """
    assert _tokens_of(source) == expected, f"matcher missed a planted token in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("x = OtherEnum.M303\n", id="m-attribute-on-an-unrelated-enum"),
        pytest.param("x = _MODELO_LABEL\n", id="constant-without-a-modelo-number"),
        pytest.param("x = _M_CASILLA\n", id="underscore-m-without-digits"),
        pytest.param('DOC = "we branch on Modelo.M303 here"\n', id="token-inside-a-string-literal"),
        pytest.param("# Modelo.M303 is handled elsewhere\nx = 1\n", id="token-inside-a-comment"),
    ),
)
def test_matcher_stays_silent_on_lookalikes(source: str) -> None:
    """The other direction: only real references to the core enum count.

    ``OtherEnum.M303`` matters structurally — the attribute name alone is not
    enough, the receiver has to be a name bound to the core ``Modelo`` enum. The
    string and comment cases are why the matcher walks the AST rather than lines:
    prose discussing a carve-out is not a carve-out.
    """
    assert _tokens_of(source) == set()


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("from x import Modelo\n_M = Modelo\ny = _M.M303\n", id="assignment-rebind"),
        pytest.param("from x import core\ny = core.Modelo.M303\n", id="dotted-receiver"),
        pytest.param('from x import Modelo\ny = Modelo["M303"]\n', id="subscript-by-member-name"),
        pytest.param('from x import Modelo\ny = getattr(Modelo, "M303")\n', id="getattr-by-member-name"),
    ),
)
def test_precondition_guard_fires_on_every_unmatchable_route(source: str) -> None:
    """Anti-tautology proof: each evading route is planted and must be refused.

    Every one of these is invisible to :func:`_per_modelo_tokens` — planting
    them there returns an empty set, which is indistinguishable from a module
    holding no carve-outs at all. The routes were enumerated from the ways
    Python can reach an enum member, not read off the matcher, so the proof does
    not inherit the blind spot it exists to cover.
    """
    assert _unmatchable_modelo_references(ast.parse(source)), f"guard missed an unmatchable route in:\n{source}"


@pytest.mark.parametrize(
    "source",
    (
        pytest.param("from x import Modelo\ny = Modelo.M303\n", id="the-matchable-direct-spelling"),
        pytest.param("from x import Modelo as _M\ny = _M.M303\n", id="the-matchable-aliased-spelling"),
        pytest.param('from x import Modelo\ny = Modelo("303")\n', id="hydrating-a-member-from-its-value"),
        pytest.param("from x import OtherEnum\n_O = OtherEnum\ny = _O.M303\n", id="rebinding-an-unrelated-enum"),
        pytest.param('y = config["Modelo"]\n', id="subscripting-something-merely-named-modelo"),
    ),
)
def test_precondition_guard_stays_silent_on_legitimate_spellings(source: str) -> None:
    """The other direction: the guard must not tax the spellings the matcher handles.

    ``Modelo("303")`` is the canonical way to hydrate a member from its stored
    registry token and must stay free — it is a call, not a by-name lookup, and
    the loader boundary depends on it. A guard that refused it would push authors
    toward the very routes this one exists to keep out.
    """
    assert _unmatchable_modelo_references(ast.parse(source)) == []
