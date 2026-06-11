"""Audit gate: calculation-test expected-value grounding.

Tautological patterns in calculation tests are forbidden: every
calculation test that asserts a hardcoded Decimal against a registry
formula must source that value from an external authority (AEAT
workbook, BOE worked example, live oracle replay, registry fixture).
Tests that hand-compute the same arithmetic the registry performs are
tautological; they prove only that Python arithmetic works, not that
the registry formula is correct against AEAT.

This file provides the real-behavior test that verifies the existing
AST-based tautology gate in ``test_tautology_gate.py`` is present and
non-vacuous (i.e. it scans a non-empty set of test functions and did
not silently become a no-op through a rename or deletion of the
scanned fixtures).

The hand-summed aggregation scanner (``_HAND_SUMMED_WAIVERS``) lists
documented waivers, each paired with an explicit external-authority
justification comment.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ....core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_TAUTOLOGY_GATE_PATH = PROJECT_ROOT / "src/aeat/domain/calculations/registry/tests/test_tautology_gate.py"
_CHAIN_BEHAVIOUR_PATH = PROJECT_ROOT / "src/aeat/domain/calculations/registry/tests/test_renta_chain_behaviour.py"


def _count_test_functions(path: Path) -> int:
    """Return the number of ``test_`` functions in ``path``."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return 0
    return sum(
        1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
    )


def test_tautology_gate_file_exists_and_is_non_vacuous() -> None:
    """The tautology gate must exist and contain at least two test functions.

    Verifies contract: if the gate is deleted or emptied, this test fails
    loudly so the audit surface is not silently disabled.
    """
    assert _TAUTOLOGY_GATE_PATH.exists(), (
        f"Tautology gate missing at {_TAUTOLOGY_GATE_PATH}; calculation grounding is unprotected — restore the file."
    )
    count = _count_test_functions(_TAUTOLOGY_GATE_PATH)
    assert count >= 2, (
        f"Tautology gate at {_TAUTOLOGY_GATE_PATH} contains only {count} "
        f"test function(s); expected >=2 (chain-behaviour + hand-summed gates). "
        f"The gate has been hollowed out."
    )


def test_chain_behaviour_suite_exists_as_gate_target() -> None:
    """The chain-behaviour test file the tautology gate scans must exist.

    The tautology gate hard-fails if the scanned file is missing.  This
    companion test surfaces the same failure earlier (as a collection
    error) so the root cause is immediately obvious.
    """
    assert _CHAIN_BEHAVIOUR_PATH.exists(), (
        f"chain-behaviour test file missing at {_CHAIN_BEHAVIOUR_PATH}; "
        f"restore it or update the tautology gate's scan target."
    )


def test_tautology_gate_waiver_set_is_empty() -> None:
    """The chain-behaviour tautology waiver set must remain empty.

    Waivers in ``_TAUTOLOGY_WAIVERS`` represent chain-behaviour scenario
    assertions that were granted an exemption from the tautology gate.
    Every entry must name an external authority.  An empty set means no
    waivers exist — the gate is operating at full strength.  If a waiver
    is added without a corresponding external-authority annotation, the
    review process (not this test) must catch it.
    """
    text = _TAUTOLOGY_GATE_PATH.read_text(encoding="utf-8")
    # Parse the frozenset literal for _TAUTOLOGY_WAIVERS.  It may be a plain
    # Assign or an annotated AnnAssign (``_TAUTOLOGY_WAIVERS: frozenset[str] = frozenset()``).
    tree = ast.parse(text)
    for node in ast.walk(tree):
        val: ast.expr | None = None
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_TAUTOLOGY_WAIVERS":
                    val = node.value
                    break
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "_TAUTOLOGY_WAIVERS":
                val = node.value
        if val is not None:
            # The value should be frozenset() — an empty frozenset call.
            if (
                isinstance(val, ast.Call)
                and isinstance(val.func, ast.Name)
                and val.func.id == "frozenset"
                and not val.args
                and not val.keywords
            ):
                return  # Empty frozenset — gate is clean.
            pytest.fail(
                "_TAUTOLOGY_WAIVERS is not an empty frozenset(); "
                "a chain-behaviour waiver was added. "
                "Confirm it names an external authority before accepting.",
            )
    pytest.fail(
        "_TAUTOLOGY_WAIVERS assignment not found in tautology gate file; "
        "the gate structure has changed — update this audit test.",
    )
