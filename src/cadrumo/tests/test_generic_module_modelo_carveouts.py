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


def _per_modelo_tokens(tree: ast.AST) -> set[str]:
    """Return the distinct per-modelo tokens referenced in ``tree``.

    A token is either a ``_M###_*`` bare name or a ``Modelo.M###`` attribute
    access on the core ``Modelo`` enum. Comments and string literals are ignored
    (the AST carries neither as identifiers), so only real code references count.
    """
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _NAME_TOKEN_RE.match(node.id):
            tokens.add(node.id)
        elif (
            isinstance(node, ast.Attribute)
            and _MODELO_ATTR_RE.match(node.attr)
            and isinstance(node.value, ast.Name)
            and node.value.id == "Modelo"
        ):
            tokens.add(f"Modelo.{node.attr}")
    return tokens


def test_per_modelo_token_set_does_not_exceed_baseline(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Each named generic module carries only previously reviewed per-modelo tokens."""
    inventory = {aeat_relative(path): tree for path, tree in production_ast_items(source_tree_ast)}
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
