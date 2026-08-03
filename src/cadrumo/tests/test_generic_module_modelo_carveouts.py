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
(``domain/calculations/registry/_formula_runtime.py``) is deliberately NOT in
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

import pytest

from ._inventory import aeat_relative, production_ast_items

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
    "application/modelo/_projection.py": frozenset(
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
    "application/modelo/_calculation_actions.py": frozenset({"Modelo.M210"}),
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
