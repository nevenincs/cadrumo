"""Ratchet: per-modelo tokens in generic application modules only decrease.

The architecture
review found per-modelo special cases accreting inside generic application
modules — modelo-branched logic keyed on ``Modelo.M###`` members or on
``_M###_*`` module constants — where dedicated per-modelo homes
(``_m303_m349_reconcile.py``, ``_m036_lifecycle.py``, ``_iva_wallet_gate.py``)
prove the codebase already knows the right shape.

This AST gate inventories those per-modelo tokens across a NAMED list of generic
modules and records a per-module baseline. The count may only DECREASE: a new
``Modelo.M###`` branch or ``_M###_*`` constant in one of these modules pushes its
distinct-token count above the baseline and fails the gate, unless the baseline
is CONSCIOUSLY lowered (never raised) — so a new per-modelo carve-out in a
generic module is a deliberate, reviewed act, not an accident.

Distinct tokens are counted (not raw occurrences) so the gate is stable under
refactors that merely add or remove a use of an existing token; only introducing
a genuinely NEW per-modelo symbol trips it.

Scope note (no silent caps): the domain formula runtime
(``domain/calculations/registry/_formula_runtime.py``) is deliberately NOT in
this list. Its per-modelo *op evaluators* (``_evaluate_m100_*`` /
``_evaluate_m210_*`` / ``_evaluate_m131_*``) are named per-modelo behaviour that
is permitted, and the module is an actively-churned dispatch surface; ratcheting
it is deferred to a follow-up once its dispatch shape stabilises. Modelo-KEYED
DATA modules (applicability rules, censo modelo sets, query projections) are out
of scope by design — only modelo-BRANCHED LOGIC in generic modules is the debt.
"""

from __future__ import annotations

import ast
import re

import pytest

from ._inventory import SRC_AEAT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ``_M###_<NAME>`` module constants (e.g. _M100_CUOTA_INTEGRA_ESTATAL_CASILLA).
_NAME_TOKEN_RE = re.compile(r"^_M\d+_")
# ``M###`` attribute of the core ``Modelo`` enum (e.g. Modelo.M303).
_MODELO_ATTR_RE = re.compile(r"^M\d+$")

_SRC_ROOT = SRC_AEAT

#: The named generic application modules under ratchet, mapped to the distinct
#: per-modelo-token baseline recorded after the architecture-remediation sweep.
#: The count for each module may only decrease. Raising a baseline is a
#: conscious, reviewed decision (a new per-modelo carve-out) — never an accident.
_RATCHET_BASELINE: dict[str, int] = {
    "application/modelo/_projection.py": 14,
    "application/modelo/_calculation_actions.py": 14,
    "application/modelo/_verification_cross_period.py": 6,
}


def _per_modelo_tokens(source: str) -> set[str]:
    """Return the distinct per-modelo tokens referenced in ``source``.

    A token is either a ``_M###_*`` bare name or a ``Modelo.M###`` attribute
    access on the core ``Modelo`` enum. Comments and string literals are ignored
    (the AST carries neither as identifiers), so only real code references count.
    """
    tree = ast.parse(source)
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


@pytest.mark.parametrize("relative_path", sorted(_RATCHET_BASELINE))
def test_per_modelo_token_count_does_not_exceed_baseline(relative_path: str) -> None:
    """Each named generic module carries no more distinct per-modelo tokens than its baseline."""
    module_path = _SRC_ROOT / relative_path
    assert module_path.is_file(), f"named ratchet module missing: {relative_path}"
    count = len(_per_modelo_tokens(module_path.read_text(encoding="utf-8")))
    baseline = _RATCHET_BASELINE[relative_path]
    assert count <= baseline, (
        f"{relative_path} now references {count} distinct per-modelo tokens, above the "
        f"ratchet baseline of {baseline}. A new per-modelo carve-out in a generic module "
        f"must move to a named `_m<id>_*` module or registry data; if this is a conscious, "
        f"reviewed addition, lower nothing — the baseline only ratchets DOWN."
    )


def test_gate_detects_an_injected_per_modelo_token_probe() -> None:
    """Anti-tautology: the token scanner actually detects a newly-injected carve-out.

    If the scanner silently missed new tokens, the ratchet would be a no-op that
    never fails. This injects a synthetic module referencing a fresh ``Modelo.M999``
    branch and a fresh ``_M999_PROBE_CASILLA`` constant and asserts both are seen —
    so a real new carve-out in a scanned module would push its count above baseline.
    """
    probe_source = (
        "from aeat.core import Modelo\n"
        "_M999_PROBE_CASILLA = 'probe'\n"
        "def handle(work_unit):\n"
        "    if work_unit.modelo is Modelo.M999:\n"
        "        return _M999_PROBE_CASILLA\n"
        "    return None\n"
    )
    tokens = _per_modelo_tokens(probe_source)
    assert "Modelo.M999" in tokens
    assert "_M999_PROBE_CASILLA" in tokens


def test_scanner_ignores_non_modelo_and_data_lookalikes() -> None:
    """The scanner counts only real per-modelo tokens, not innocent lookalikes.

    ``_METHOD_`` / ``_MAX_`` style names and a non-``Modelo`` ``M303`` attribute
    must NOT be counted, or the ratchet would flag benign code and train reviewers
    to raise baselines reflexively.
    """
    benign_source = (
        "_MAX_ROWS = 10\n"
        "_METRIC_NAME = 'x'\n"
        "class Other:\n"
        "    M303 = 1\n"
        "def f(other):\n"
        "    return other.M303 + _MAX_ROWS\n"
    )
    assert _per_modelo_tokens(benign_source) == set()
